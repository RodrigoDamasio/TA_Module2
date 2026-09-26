"""Context-window management: token estimates, budgets, and structure-aware chunking."""

import math
from dataclasses import dataclass

from app.domain.code import CodeChunk, number_line
from app.domain.errors import CodeTooLarge
from app.domain.models import Language
from app.tools.metrics import FunctionInfo, analyze_functions

CHARS_PER_TOKEN = 3  # conservative for code (Module 1 measured ~3.1)
TOOL_TRAFFIC_RESERVE = 2000  # tokens kept free for tool calls + trimmed results

_IMPORT_PREFIXES = {
    Language.PYTHON: ("import ", "from "),
    Language.JAVASCRIPT: ("import ", "const ", "require("),
    Language.TYPESCRIPT: ("import ",),
    Language.JAVA: ("import ", "package "),
    Language.GO: ("import ", "package "),
}


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass
class Budget:
    """Tracks estimated tokens in the conversation against the per-request budget."""

    total: int
    used: int = 0

    def add(self, text: str | None) -> None:
        self.used += estimate_tokens(text or "")

    def room_for(self, tokens: int) -> bool:
        return self.used + tokens <= self.total


def top_level(functions: list[FunctionInfo]) -> list[FunctionInfo]:
    kept: list[FunctionInfo] = []
    for f in sorted(functions, key=lambda f: (f.start, -f.end)):
        if not kept or f.start > kept[-1].end:
            kept.append(f)
    return kept


def _preferred_cuts(lines: list[str], functions: list[FunctionInfo]) -> set[int]:
    """Line numbers where a chunk may start: each top-level function, moved up over its
    decorators/comments so they stay together."""
    cuts = set()
    for f in top_level(functions):
        start = f.start
        while start > 1 and lines[start - 2].strip().startswith(("@", "#", "//", "/*", "*")):
            start -= 1
        cuts.add(start)
    return cuts


def outline(functions: list[FunctionInfo]) -> str:
    items = [f"- {f.name} (lines {f.start}-{f.end})" for f in top_level(functions)]
    return "\n".join(items) or "- (no functions detected)"


def imports(lines: list[str], language: Language) -> str:
    found = [ln.strip() for ln in lines if ln.strip().startswith(_IMPORT_PREFIXES[language])]
    return "\n".join(found[:30]) or "(none)"


class ChunkPlanner:
    def __init__(self, code_allowance_tokens: int, max_chunks: int) -> None:
        self._allowance = code_allowance_tokens
        self._max_chunks = max_chunks

    def plan(self, code: str, language: Language, header_template=None) -> list[CodeChunk]:
        """Split code into chunks that each fit the code allowance.

        header_template(outline, imports) -> str renders the context header given to every
        chunk of a split file; its size is subtracted from the allowance.
        """
        lines = code.splitlines() or [""]
        whole = CodeChunk(tuple(lines), 1, language)
        if estimate_tokens(whole.numbered()) <= self._allowance:
            return [whole]

        functions = analyze_functions(code, language)
        header = ""
        if header_template is not None:
            header = header_template(outline(functions), imports(lines, language))
        allowance_chars = (self._allowance - estimate_tokens(header)) * CHARS_PER_TOKEN
        if allowance_chars <= 0:
            raise CodeTooLarge("The context budget is too small to analyze this code.")

        ranges = self._split(lines, _preferred_cuts(lines, functions), allowance_chars)
        if len(ranges) > self._max_chunks:
            raise CodeTooLarge(
                f"The code would need {len(ranges)} parts; the maximum is {self._max_chunks}."
            )
        return [
            CodeChunk(tuple(lines[s - 1 : e]), s, language, i, len(ranges), header)
            for i, (s, e) in enumerate(ranges, 1)
        ]

    @staticmethod
    def _split(lines: list[str], cuts: set[int], allowance_chars: int) -> list[tuple[int, int]]:
        """Greedy packing; when full, cut at the last function boundary, else the last blank
        line, else right here."""
        ranges: list[tuple[int, int]] = []
        start, size = 1, 0
        n = 1
        while n <= len(lines):
            cost = len(number_line(n, lines[n - 1])) + 1
            if size + cost > allowance_chars and n > start:
                candidates = [c for c in cuts if start < c <= n]
                blanks = [i for i in range(start + 1, n + 1) if not lines[i - 2].strip()]
                cut = max(candidates) if candidates else (max(blanks) if blanks else n)
                ranges.append((start, cut - 1))
                start, size = cut, 0
                n = cut
                continue
            size += cost
            n += 1
        ranges.append((start, len(lines)))
        return ranges
