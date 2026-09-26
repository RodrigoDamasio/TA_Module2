"""SQLite result cache — the only module with SQL. Values are always bound parameters."""

import sqlite3
from pathlib import Path

from app.domain.models import AnalysisResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    key            TEXT PRIMARY KEY,
    result_json    TEXT NOT NULL,
    model          TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
_GET = "SELECT result_json FROM analyses WHERE key = ?"
_PUT = (
    "INSERT OR REPLACE INTO analyses (key, result_json, model, prompt_version) VALUES (?, ?, ?, ?)"
)


class SqliteAnalysisCache:
    def __init__(self, path: str) -> None:
        self._path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def get(self, key: str) -> AnalysisResult | None:
        with self._connect() as conn:
            row = conn.execute(_GET, (key,)).fetchone()
        return AnalysisResult.model_validate_json(row[0]) if row else None

    def put(self, key: str, result: AnalysisResult) -> None:
        with self._connect() as conn:
            conn.execute(
                _PUT,
                (key, result.model_dump_json(), result.meta.model, result.meta.prompt_version),
            )
