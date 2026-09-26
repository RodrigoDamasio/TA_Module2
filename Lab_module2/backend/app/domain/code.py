from dataclasses import dataclass

from .models import Language

LINE_SEPARATOR = "│"


def number_line(n: int, line: str) -> str:
    return f"{n:>4}{LINE_SEPARATOR} {line}"


@dataclass(frozen=True)
class CodeChunk:
    """A contiguous slice of a source file that keeps the file's original line numbers."""

    lines: tuple[str, ...]
    first_line: int
    language: Language
    index: int = 1
    total: int = 1
    header: str = ""

    @property
    def last_line(self) -> int:
        return self.first_line + len(self.lines) - 1

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def numbered(self) -> str:
        return "\n".join(number_line(self.first_line + i, ln) for i, ln in enumerate(self.lines))
