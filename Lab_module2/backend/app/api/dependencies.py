"""Wiring: the only place that chooses concrete implementations."""

from functools import lru_cache

from fastapi import Depends

from app.application.analyze import AnalyzeCode
from app.application.prompts import PromptLibrary
from app.config import Settings, get_settings
from app.domain.ports import AnalysisCache, LLMClient
from app.infrastructure.demo_llm import DemoLLMClient
from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.llm_decorators import (
    CircuitBreakerLLMClient,
    ConcurrencyLimitedLLMClient,
    PacedLLMClient,
    RetryingLLMClient,
)
from app.infrastructure.samples import SampleStore
from app.infrastructure.sqlite_cache import SqliteAnalysisCache

from .guards import RateLimiter


@lru_cache
def _llm(mode: str, model: str, api_key: str | None, interval: float, timeout: int) -> LLMClient:
    if mode == "fake":
        return DemoLLMClient()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set (or use LLM_MODE=fake).")
    gemini = GeminiClient(api_key, model, timeout)
    return CircuitBreakerLLMClient(
        RetryingLLMClient(ConcurrencyLimitedLLMClient(PacedLLMClient(gemini, interval)))
    )


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient:
    return _llm(
        settings.llm_mode,
        settings.gemini_model,
        settings.google_api_key,
        settings.llm_min_interval_s,
        settings.llm_timeout_s,
    )


@lru_cache
def _cache(path: str) -> SqliteAnalysisCache:
    return SqliteAnalysisCache(path)


def get_cache(settings: Settings = Depends(get_settings)) -> AnalysisCache:
    return _cache(settings.database_path)


@lru_cache
def get_prompts() -> PromptLibrary:
    return PromptLibrary()


@lru_cache
def get_samples() -> SampleStore:
    return SampleStore()


@lru_cache
def _limiter(per_minute: int, per_day: int) -> RateLimiter:
    return RateLimiter(per_minute, per_day)


def get_rate_limiter(settings: Settings = Depends(get_settings)) -> RateLimiter:
    return _limiter(settings.rate_limit_per_minute, settings.rate_limit_per_day)


def get_analyze(
    llm: LLMClient = Depends(get_llm),
    cache: AnalysisCache = Depends(get_cache),
    prompts: PromptLibrary = Depends(get_prompts),
    settings: Settings = Depends(get_settings),
) -> AnalyzeCode:
    return AnalyzeCode(llm, cache, prompts, settings)
