"""Loads the prompt library (app/prompts) and assembles prompts for each phase."""

import re
from functools import cache
from pathlib import Path

from app.domain.code import CodeChunk
from app.domain.models import AnalysisType, Language

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

# Every placeholder used by the prompt files; none may survive assembly.
PLACEHOLDERS = frozenset(
    {
        "persona",
        "language",
        "analysis_type",
        "language_checklist",
        "few_shot_examples",
        "max_tool_rounds",
        "chunk_header",
        "numbered_code",
        "validation_errors",
        "index",
        "total",
        "start",
        "end",
        "outline",
        "imports",
    }
)


def fill(template: str, **values: object) -> str:
    """Replace only the given {placeholders}; any other braces (e.g. JSON) stay as they are."""
    return _PLACEHOLDER.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template
    )


class PromptLibrary:
    def __init__(self, root: Path = PROMPTS_DIR) -> None:
        self._root = root

    @cache  # noqa: B019 — one library instance per process; files never change at runtime
    def _read(self, name: str) -> str:
        return (self._root / name).read_text().strip()

    @property
    def version(self) -> str:
        return self._read("VERSION")

    def system(self, analysis_type: AnalysisType, language: Language) -> str:
        return fill(
            self._read("base.md"),
            persona=self._read(f"personas/{analysis_type.value}.md"),
            language=language.value,
            analysis_type=analysis_type.value,
            language_checklist=self._read(f"languages/{language.value}.md"),
            few_shot_examples=self._read("examples.md"),
        )

    def chunk_header(self, outline: str, imports: str) -> str:
        """Static part of the header shared by every chunk; position is filled per chunk."""
        return fill(self._read("chunk_header.md"), outline=outline, imports=imports)

    def investigate(self, analysis_type: AnalysisType, chunk: CodeChunk, max_rounds: int) -> str:
        header = ""
        if chunk.total > 1:
            header = fill(
                chunk.header,
                index=chunk.index,
                total=chunk.total,
                start=chunk.first_line,
                end=chunk.last_line,
            )
        return fill(
            self._read("investigate.md"),
            analysis_type=analysis_type.value,
            max_tool_rounds=max_rounds,
            chunk_header=header,
            language=chunk.language.value,
            numbered_code=chunk.numbered(),
        )

    def report(self, analysis_type: AnalysisType) -> str:
        return fill(self._read("report.md"), analysis_type=analysis_type.value)

    def repair(self, validation_errors: str) -> str:
        return fill(self._read("repair.md"), validation_errors=validation_errors)

    def shorter(self) -> str:
        return self._read("shorter.md")
