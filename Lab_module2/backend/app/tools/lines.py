from app.domain.code import CodeChunk, number_line

MAX_READ_LINES = 30  # 30 numbered lines stay under the 2,000-char tool-result limit
MAX_FIND_HITS = 20
MAX_FIND_TEXT = 80


def read_lines(chunk: CodeChunk, start: int, end: int) -> str:
    start = max(start, chunk.first_line)
    end = min(end, chunk.last_line, start + MAX_READ_LINES - 1)
    if start > end:
        return f"No lines in range. This part covers lines {chunk.first_line}-{chunk.last_line}."
    return "\n".join(
        number_line(n, chunk.lines[n - chunk.first_line]) for n in range(start, end + 1)
    )


def find_text(chunk: CodeChunk, text: str) -> str:
    """Plain, case-insensitive substring search — never a regex (no ReDoS from model input)."""
    needle = text.strip().lower()
    if not needle or len(needle) > MAX_FIND_TEXT:
        return f"Search text must be 1-{MAX_FIND_TEXT} characters."
    hits = [
        number_line(chunk.first_line + i, line)
        for i, line in enumerate(chunk.lines)
        if needle in line.lower()
    ]
    if not hits:
        return f"No occurrences of {text!r}."
    extra = f"\n... {len(hits) - MAX_FIND_HITS} more" if len(hits) > MAX_FIND_HITS else ""
    return "\n".join(hits[:MAX_FIND_HITS]) + extra
