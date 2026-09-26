import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None
    gemini_model: str
    llm_mode: str  # gemini | fake
    llm_min_interval_s: float
    llm_timeout_s: int
    context_budget_tokens: int
    output_reserve_tokens: int
    thinking_budget: int
    max_tool_rounds: int
    max_chunks: int
    max_code_chars: int
    max_code_lines: int
    rate_limit_per_minute: int
    rate_limit_per_day: int
    database_path: str
    base_url: str
    frontend_origins: list[str]


def get_settings() -> Settings:
    return Settings(
        google_api_key=os.getenv("GOOGLE_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        llm_mode=os.getenv("LLM_MODE", "gemini"),
        llm_min_interval_s=_float("LLM_MIN_INTERVAL_S", 6.0),
        llm_timeout_s=_int("LLM_TIMEOUT_S", 60),
        context_budget_tokens=_int("CONTEXT_BUDGET_TOKENS", 16000),
        output_reserve_tokens=_int("OUTPUT_RESERVE_TOKENS", 4000),
        thinking_budget=_int("THINKING_BUDGET", 1024),
        max_tool_rounds=_int("MAX_TOOL_ROUNDS", 3),
        max_chunks=_int("MAX_CHUNKS", 4),
        max_code_chars=_int("MAX_CODE_CHARS", 60000),
        max_code_lines=_int("MAX_CODE_LINES", 2000),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 5),
        rate_limit_per_day=_int("RATE_LIMIT_PER_DAY", 50),
        database_path=os.getenv("DATABASE_PATH", "analyzer.db"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        frontend_origins=[
            origin.strip().rstrip("/")
            for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
            if origin.strip()
        ],
    )
