import json

import pytest

from app.application.context import (
    CHARS_PER_TOKEN,
    ChunkPlanner,
    estimate_tokens,
    imports,
    outline,
)
from app.domain.code import CodeChunk
from app.domain.errors import CodeTooLarge
from app.domain.models import Language
from app.domain.ports import ToolCall
from app.tools.metrics import analyze_functions, code_metrics, complexity_hint
from app.tools.registry import MAX_RESULT_CHARS, TOOL_SPECS, ToolRunner

PY = """import os
from typing import Any


def simple(a):
    return a + 1


def branchy(a, b):
    if a:
        return 1
    for x in b:
        if x > 2 and x < 5:
            return x
    return 0
"""


def make_module(n_functions: int, body_lines: int = 6) -> str:
    parts = ["import os", ""]
    for n in range(n_functions):
        parts.append(f"def func_{n}(value):")
        parts += [
            f"    value = value + {k}  # step {k} of the calculation" for k in range(body_lines)
        ]
        parts += ["    return value", ""]
    return "\n".join(parts)


# T1
def test_metrics_match_lizard_values():
    functions = {f.name: f.complexity for f in analyze_functions(PY, Language.PYTHON)}
    assert functions == {"simple": 1, "branchy": 5}
    metrics = code_metrics(PY, Language.PYTHON)
    assert metrics["functions"] == 2
    assert metrics["max_complexity"] == 5
    assert metrics["complexity_hint"] == "low"
    assert metrics["per_function"][0]["name"] == "branchy"


@pytest.mark.parametrize(
    "ccn, hint", [(1, "low"), (5, "low"), (6, "medium"), (10, "medium"), (11, "high")]
)
def test_complexity_hint(ccn, hint):
    assert complexity_hint(ccn) == hint


@pytest.mark.parametrize(
    "language, code",
    [
        (Language.JAVASCRIPT, "function f(a) { if (a) { return 1 } return 0 }"),
        (Language.TYPESCRIPT, "function f(a: number): number { return a > 1 ? 1 : 0 }"),
        (Language.JAVA, "class A { int f(int a) { if (a > 1) { return 1; } return 0; } }"),
        (Language.GO, "package main\nfunc f(a int) int { if a > 1 { return 1 }; return 0 }"),
    ],
)
def test_metrics_support_all_languages(language, code):
    assert analyze_functions(code, language)[0].complexity == 2


def chunk(code=PY, first_line=1):
    return CodeChunk(tuple(code.splitlines()), first_line, Language.PYTHON)


def run(tool, args=None, c=None):
    return ToolRunner(c or chunk()).run(ToolCall("1", tool, args or {})).content


# T2
def test_read_lines_is_numbered_and_clamped():
    out = run("read_lines", {"start": 0, "end": 6}, chunk())
    assert out.splitlines()[0] == "   1│ import os"
    assert out.splitlines()[-1].startswith("   6│")
    assert "No lines in range" in run("read_lines", {"start": 500, "end": 600})
    long = run("read_lines", {"start": 1, "end": 500}, chunk(make_module(20)))
    assert len(long.splitlines()) == 30 and "truncated" not in long


def test_tools_keep_original_line_numbers_in_a_later_chunk():
    later = chunk(first_line=100)
    assert run("read_lines", {"start": 104, "end": 104}, later).startswith(" 104│ def simple")
    metrics = json.loads(run("get_code_metrics", c=later))
    assert {f["lines"] for f in metrics["per_function"]} == {"104-105", "108-114"}


# T3
def test_find_text_is_plain_case_insensitive_and_capped():
    assert run("find_text", {"text": "RETURN"}).count("│") == 4
    assert run("find_text", {"text": ".*"}) == "No occurrences of '.*'."  # not a regex
    many = run("find_text", {"text": "value"}, chunk(make_module(10)))
    assert many.count("│") == 20 and "more" in many
    assert "1-80 characters" in run("find_text", {"text": "x" * 81})


# T4 + G8 (tool side)
def test_results_are_trimmed_and_errors_are_messages():
    big = chunk(make_module(80, body_lines=2))
    assert len(run("get_code_metrics", c=big)) <= MAX_RESULT_CHARS
    assert run("delete_files").startswith("Error: unknown tool")
    assert run("read_lines", {"start": "x"}).startswith("Error: invalid arguments")
    assert {t.name for t in TOOL_SPECS} == {"get_code_metrics", "read_lines", "find_text"}


# X1
def test_estimate_is_conservative():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("x" * 300) == 300 // CHARS_PER_TOKEN
    assert estimate_tokens("x" * 300) >= 300 // 4


# X2
def test_small_file_is_one_chunk():
    chunks = ChunkPlanner(8000, 4).plan(PY, Language.PYTHON)
    assert len(chunks) == 1 and chunks[0].first_line == 1 and chunks[0].header == ""


# X3
def test_large_file_splits_at_function_boundaries_without_losing_lines():
    code = make_module(12)
    lines = code.splitlines()
    chunks = ChunkPlanner(600, 10).plan(code, Language.PYTHON, lambda o, i: "HEADER")

    assert len(chunks) > 1
    assert [ln for c in chunks for ln in c.lines] == lines  # every line exactly once
    for c in chunks[1:]:
        assert c.lines[0].startswith("def func_")  # cut at a function boundary
        assert c.header == "HEADER" and c.total == len(chunks)
    assert chunks[1].first_line == len(chunks[0].lines) + 1


# X4
def test_giant_function_is_split_at_blank_lines_and_fits():
    body = []
    for block in range(30):
        body += [f"    total += {k} * {block}  # accumulate" for k in range(5)] + [""]
    code = "def giant(total):\n" + "\n".join(body) + "    return total\n"
    chunks = ChunkPlanner(500, 20).plan(code, Language.PYTHON)

    assert len(chunks) > 1
    assert all(estimate_tokens(c.numbered()) <= 500 for c in chunks)
    assert all(not code.splitlines()[c.first_line - 2].strip() for c in chunks[1:])


# X5
def test_too_many_chunks_is_rejected():
    with pytest.raises(CodeTooLarge, match="maximum is 2"):
        ChunkPlanner(300, 2).plan(make_module(20), Language.PYTHON)


# X7 (outline/imports feed the chunk header)
def test_outline_and_imports():
    functions = analyze_functions(PY, Language.PYTHON)
    assert outline(functions) == "- simple (lines 5-6)\n- branchy (lines 9-15)"
    assert imports(PY.splitlines(), Language.PYTHON) == "import os\nfrom typing import Any"
    assert imports(["x = 1"], Language.GO) == "(none)"
