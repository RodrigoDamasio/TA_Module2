"""Two-phase agent: investigate (chain-of-thought + tools) → report (schema-constrained JSON)."""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.config import Settings
from app.domain.code import CodeChunk
from app.domain.errors import LLMBadResponse
from app.domain.models import (
    MAX_ISSUES,
    MAX_SUGGESTIONS,
    AnalysisReport,
    AnalysisType,
    LLMReport,
    Severity,
)
from app.domain.ports import (
    AssistantMessage,
    LLMClient,
    LLMRequest,
    LLMResponse,
    Message,
    TokenUsage,
    ToolResultsMessage,
    UserMessage,
)
from app.tools.registry import TOOL_SPECS, ToolRunner

from .context import Budget
from .prompts import PromptLibrary

INVESTIGATE_MAX_OUTPUT = 1500
_TEXT_LIMITS = {"description": 600, "suggestion": 800}


@dataclass
class PartialResult:
    report: AnalysisReport
    usage: TokenUsage
    llm_calls: int
    tool_rounds: int
    truncated: bool
    dropped_issues: int


def _normalize(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Cheap local fixes that would otherwise cost a repair call: cap lists, shorten
    over-long texts, drop issues with impossible line numbers."""
    issues = [i for i in data.get("issues") or [] if isinstance(i, dict)]
    kept = [i for i in issues if isinstance(i.get("line"), int) and i["line"] >= 1]
    dropped = len(issues) - len(kept)

    def rank(issue: dict[str, Any]) -> int:
        try:
            return Severity(issue.get("severity")).rank
        except ValueError:
            return -1

    kept = sorted(kept, key=rank, reverse=True)[:MAX_ISSUES]
    for issue in kept:
        for field, limit in _TEXT_LIMITS.items():
            if isinstance(issue.get(field), str) and len(issue[field]) > limit:
                issue[field] = issue[field][: limit - 1] + "…"
    summary = data.get("summary")
    if isinstance(summary, str) and len(summary) > 800:
        data["summary"] = summary[:799] + "…"
    data["issues"] = kept
    data["suggestions"] = (data.get("suggestions") or [])[:MAX_SUGGESTIONS]
    return data, dropped


def _parse(response: LLMResponse) -> dict[str, Any] | None:
    if response.parsed is not None:
        return dict(response.parsed)
    try:
        value = json.loads(response.text or "")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _errors_text(err: ValidationError) -> str:
    return "\n".join(
        f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()[:10]
    )


class Agent:
    def __init__(self, llm: LLMClient, prompts: PromptLibrary, settings: Settings) -> None:
        self._llm = llm
        self._prompts = prompts
        self._settings = settings

    def run(self, analysis_type: AnalysisType, chunk: CodeChunk, max_rounds: int) -> PartialResult:
        self._usage = TokenUsage()
        self._calls = 0
        system = self._prompts.system(analysis_type, chunk.language)
        task = self._prompts.investigate(analysis_type, chunk, max_rounds)
        notes, rounds = self._investigate(system, task, chunk, max_rounds)
        report, truncated, dropped = self._report(system, task, notes, analysis_type)
        return PartialResult(report, self._usage, self._calls, rounds, truncated, dropped)

    # ---- phase 1 ------------------------------------------------------------

    def _investigate(
        self, system: str, task: str, chunk: CodeChunk, max_rounds: int
    ) -> tuple[str, int]:
        budget = Budget(self._settings.context_budget_tokens)
        budget.add(system)
        budget.add(task)
        reserve = self._settings.output_reserve_tokens + INVESTIGATE_MAX_OUTPUT
        messages: list[Message] = [UserMessage(task)]
        runner = ToolRunner(chunk)
        notes: list[str] = []
        rounds = 0

        response = self._call(system, messages, tools=max_rounds > 0)
        while True:
            messages.append(response.as_message())
            budget.add(response.text)
            if response.text:
                notes.append(response.text.strip())
            if not response.tool_calls:
                break
            results = [runner.run(call) for call in response.tool_calls]
            messages.append(ToolResultsMessage(results))
            for result in results:
                budget.add(result.content)
                notes.append(f"Tool {result.name} returned:\n{result.content}")
            rounds += 1
            if rounds >= max_rounds or not budget.room_for(reserve):
                break  # round cap or finalize-when-low
            response = self._call(system, messages, tools=True)
        return "\n\n".join(notes) or "(no notes)", rounds

    # ---- phase 2 ------------------------------------------------------------

    def _report(
        self, system: str, task: str, notes: str, analysis_type: AnalysisType
    ) -> tuple[AnalysisReport, bool, int]:
        # Compacted conversation: code + investigation notes, no raw tool-call turns.
        messages: list[Message] = [
            UserMessage(task),
            AssistantMessage(f"Investigation notes:\n{notes}", []),
            UserMessage(self._prompts.report(analysis_type)),
        ]
        response = self._call(system, messages, schema=True)
        truncated = False
        if response.finish_reason == "max_tokens":
            messages += [AssistantMessage(response.text, []), UserMessage(self._prompts.shorter())]
            response = self._call(system, messages, schema=True)
            truncated = response.finish_reason == "max_tokens"

        data = _parse(response)
        try:
            report, dropped = self._validate(data)
            return report, truncated, dropped
        except (ValidationError, TypeError) as err:
            if truncated:
                raise LLMBadResponse("The model's answer was cut off and is not valid.") from err
            detail = _errors_text(err) if isinstance(err, ValidationError) else "not a JSON object"
            messages += [
                AssistantMessage(response.text, []),
                UserMessage(self._prompts.repair(detail)),
            ]
            response = self._call(system, messages, schema=True)
            try:
                report, dropped = self._validate(_parse(response))
            except (ValidationError, TypeError) as err2:
                raise LLMBadResponse("The model's answer did not match the schema.") from err2
            return report, response.finish_reason == "max_tokens", dropped

    @staticmethod
    def _validate(data: dict[str, Any] | None) -> tuple[AnalysisReport, int]:
        if data is None:
            raise TypeError("no JSON object")
        normalized, dropped = _normalize(data)
        return AnalysisReport.model_validate(normalized), dropped

    # ---- LLM call -------------------------------------------------------------

    def _call(
        self, system: str, messages: list[Message], tools: bool = False, schema: bool = False
    ) -> LLMResponse:
        request = LLMRequest(
            system=system,
            messages=list(messages),
            tools=TOOL_SPECS if tools else [],
            response_schema=LLMReport if schema else None,
            max_output_tokens=(
                self._settings.output_reserve_tokens if schema else INVESTIGATE_MAX_OUTPUT
            ),
            thinking_budget=0 if schema else self._settings.thinking_budget,
        )
        response = self._llm.generate(request)
        self._calls += 1
        self._usage = self._usage + response.usage
        return response
