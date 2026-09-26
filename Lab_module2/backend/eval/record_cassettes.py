"""Record raw Gemini responses from ONE real analysis into tests/cassettes/ (spends ~2-4 calls).

python -m eval.record_cassettes
"""

import dataclasses
import json
import tempfile
from pathlib import Path

from app.application.analyze import AnalyzeCode
from app.application.prompts import PromptLibrary
from app.config import get_settings
from app.domain.models import AnalysisRequest
from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.llm_decorators import PacedLLMClient, RetryingLLMClient
from app.infrastructure.sqlite_cache import SqliteAnalysisCache

CASSETTES = Path(__file__).resolve().parents[1] / "tests" / "cassettes"


def main() -> None:
    settings = get_settings()
    CASSETTES.mkdir(exist_ok=True)
    recorded: list[dict] = []

    def keep(raw) -> None:
        # `parsed` is derived by the SDK, not part of Gemini's response
        recorded.append(raw.model_dump(mode="json", exclude_none=True, exclude={"parsed"}))

    gemini = GeminiClient(settings.google_api_key, settings.gemini_model, 60, on_raw=keep)
    llm = RetryingLLMClient(PacedLLMClient(gemini, settings.llm_min_interval_s))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SqliteAnalysisCache(f"{tmp}/c.db")
            settings = dataclasses.replace(settings, database_path=f"{tmp}/c.db")
            sample = Path(__file__).resolve().parents[1] / "samples/python/sql_injection.py"
            result = AnalyzeCode(llm, cache, PromptLibrary(), settings)(
                AnalysisRequest(
                    code=sample.read_text(), language="python", analysis_type="security"
                )
            )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:  # keep every paid-for response, even if the run failed
        for n, raw in enumerate(recorded, 1):
            (CASSETTES / f"sql_injection_security_{n}.json").write_text(json.dumps(raw, indent=2))
        print(f"\nrecorded {len(recorded)} responses → {CASSETTES}")


if __name__ == "__main__":
    main()
