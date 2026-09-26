"""Sample corpus served by /samples: code files + stored results (0 LLM calls)."""

import json
from functools import cache
from pathlib import Path

from app.domain.models import AnalysisResult, AnalysisType

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


class SampleStore:
    def __init__(self, root: Path = SAMPLES_DIR) -> None:
        self._root = root

    @cache  # noqa: B019 — one store per process; files never change at runtime
    def catalog(self) -> list[dict]:
        entries = json.loads((self._root / "expected.json").read_text())["samples"]
        return [
            {k: e[k] for k in ("id", "title", "language", "description", "analysis_types")}
            | {"file": e["file"]}
            for e in entries
        ]

    def get(self, sample_id: str) -> dict | None:
        return next((s for s in self.catalog() if s["id"] == sample_id), None)

    def code(self, sample: dict) -> str:
        return (self._root / sample["file"]).read_text()

    def stored_result(self, sample_id: str, analysis_type: AnalysisType) -> AnalysisResult | None:
        path = self._root / "results" / f"{sample_id}.{analysis_type.value}.json"
        if not path.is_file():
            return None
        result = AnalysisResult.model_validate_json(path.read_text())
        return result.model_copy(update={"meta": result.meta.model_copy(update={"cached": True})})
