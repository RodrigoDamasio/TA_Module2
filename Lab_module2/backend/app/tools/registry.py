"""The agent's tools: specs sent to the model + safe dispatch."""

import json

from app.domain.code import CodeChunk
from app.domain.ports import ToolCall, ToolResult, ToolSpec

from .lines import MAX_FIND_TEXT, MAX_READ_LINES, find_text, read_lines
from .metrics import code_metrics

MAX_RESULT_CHARS = 2000

TOOL_SPECS = [
    ToolSpec(
        name="get_code_metrics",
        description=(
            "Measure the code: lines of code, number of functions, and cyclomatic complexity "
            "per function with line ranges. Use it to judge complexity."
        ),
        parameters={"type": "object", "properties": {}},
    ),
    ToolSpec(
        name="read_lines",
        description=f"Re-read an exact numbered line range (at most {MAX_READ_LINES} lines).",
        parameters={
            "type": "object",
            "properties": {
                "start": {"type": "integer", "description": "First line number"},
                "end": {"type": "integer", "description": "Last line number"},
            },
            "required": ["start", "end"],
        },
    ),
    ToolSpec(
        name="find_text",
        description=(
            "Find every line containing a plain text (case-insensitive, not a regex), e.g. "
            "'execute(' or 'innerHTML'. Returns numbered lines."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": f"1-{MAX_FIND_TEXT} characters"}
            },
            "required": ["text"],
        },
    ),
]


_TRUNCATED = "\n... [truncated to fit the context budget]"


def _trim(text: str) -> str:
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[: MAX_RESULT_CHARS - len(_TRUNCATED)] + _TRUNCATED


class ToolRunner:
    def __init__(self, chunk: CodeChunk) -> None:
        self._chunk = chunk

    def run(self, call: ToolCall) -> ToolResult:
        try:
            content = self._dispatch(call)
        except (KeyError, TypeError, ValueError) as err:
            # Bad arguments go back to the model as a message; the loop continues.
            content = f"Error: invalid arguments for {call.name}: {err}"
        return ToolResult(call.id, call.name, _trim(content))

    def _dispatch(self, call: ToolCall) -> str:
        chunk, args = self._chunk, call.args
        if call.name == "get_code_metrics":
            offset = chunk.first_line - 1
            return json.dumps(code_metrics(chunk.text, chunk.language, offset))
        if call.name == "read_lines":
            return read_lines(chunk, int(args["start"]), int(args["end"]))
        if call.name == "find_text":
            return find_text(chunk, str(args["text"]))
        return f"Error: unknown tool {call.name!r}. Available: " + ", ".join(
            t.name for t in TOOL_SPECS
        )
