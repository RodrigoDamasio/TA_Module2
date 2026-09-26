"""AnalyzeCode use case: size check → cache → chunk plan → agent per chunk → merge → cache."""

import hashlib
import json

from app.config import Settings
from app.domain.errors import CodeTooLarge
from app.domain.models import AnalysisMeta, AnalysisRequest, AnalysisResult, TokenCounts
from app.domain.ports import AnalysisCache, LLMClient, TokenUsage

from .agent import INVESTIGATE_MAX_OUTPUT, Agent
from .context import TOOL_TRAFFIC_RESERVE, ChunkPlanner, estimate_tokens
from .postprocess import merge
from .prompts import PromptLibrary


def cache_key(req: AnalysisRequest, model: str, prompt_version: str) -> str:
    payload = json.dumps(
        [req.code, str(req.language), str(req.analysis_type), model, prompt_version]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def check_size(code: str, settings: Settings) -> None:
    if len(code) > settings.max_code_chars:
        raise CodeTooLarge(
            f"The code has {len(code)} characters; the maximum is {settings.max_code_chars}."
        )
    lines = code.count("\n") + 1
    if lines > settings.max_code_lines:
        raise CodeTooLarge(f"The code has {lines} lines; the maximum is {settings.max_code_lines}.")


class AnalyzeCode:
    def __init__(
        self, llm: LLMClient, cache: AnalysisCache, prompts: PromptLibrary, settings: Settings
    ) -> None:
        self._agent = Agent(llm, prompts, settings)
        self._cache = cache
        self._prompts = prompts
        self._settings = settings

    def _key(self, req: AnalysisRequest) -> str:
        return cache_key(req, self._settings.gemini_model, self._prompts.version)

    def lookup(self, req: AnalysisRequest) -> AnalysisResult | None:
        """Cached result (0 LLM calls), or None. Size is checked first."""
        check_size(req.code, self._settings)
        hit = self._cache.get(self._key(req))
        if hit is None:
            return None
        return hit.model_copy(update={"meta": hit.meta.model_copy(update={"cached": True})})

    def code_allowance(self, req: AnalysisRequest) -> int:
        """Tokens left for code in one request after the fixed prompt parts and reserves."""
        fixed = self._prompts.system(req.analysis_type, req.language) + self._prompts.report(
            req.analysis_type
        )
        return (
            self._settings.context_budget_tokens
            - estimate_tokens(fixed)
            - 300  # investigate template around the code
            - self._settings.output_reserve_tokens
            - INVESTIGATE_MAX_OUTPUT
            - TOOL_TRAFFIC_RESERVE
        )

    def __call__(self, req: AnalysisRequest) -> AnalysisResult:
        if cached := self.lookup(req):
            return cached

        planner = ChunkPlanner(self.code_allowance(req), self._settings.max_chunks)
        chunks = planner.plan(req.code, req.language, self._prompts.chunk_header)
        max_rounds = (
            self._settings.max_tool_rounds
            if len(chunks) == 1
            else min(1, self._settings.max_tool_rounds)
        )
        partials = [self._agent.run(req.analysis_type, c, max_rounds) for c in chunks]

        total_lines = req.code.count("\n") + 1
        report, dropped = merge([p.report for p in partials], total_lines)
        usage = sum((p.usage for p in partials), TokenUsage())
        result = AnalysisResult(
            **report.model_dump(),
            meta=AnalysisMeta(
                analysis_type=req.analysis_type,
                language=req.language,
                model=self._settings.gemini_model,
                prompt_version=self._prompts.version,
                chunks=len(chunks),
                tool_rounds=sum(p.tool_rounds for p in partials),
                llm_calls=sum(p.llm_calls for p in partials),
                tokens=TokenCounts(input=usage.input, output=usage.output, thinking=usage.thinking),
                truncated=any(p.truncated for p in partials),
                dropped_issues=dropped + sum(p.dropped_issues for p in partials),
            ),
        )
        self._cache.put(self._key(req), result)
        return result
