"""Scoring logic of the evaluation harness — 0 LLM calls."""

from eval.run import cases, matches, score

EXP = {
    "name": "SQLi",
    "categories": ["security"],
    "lines": [7, 8],
    "tolerance": 1,
    "min_severity": "high",
}


def issue(line=7, category="security", severity="critical"):
    return {"line": line, "category": category, "severity": severity}


def test_match_needs_category_line_and_severity():
    assert matches(issue(), EXP)
    assert matches(issue(line=9), EXP)  # within tolerance of 8
    assert not matches(issue(line=10), EXP)
    assert not matches(issue(category="bug"), EXP)
    assert not matches(issue(severity="medium"), EXP)


def meta():
    return {
        "dropped_issues": 0,
        "llm_calls": 3,
        "chunks": 1,
        "tool_rounds": 1,
        "tokens": {"input": 10, "output": 5, "thinking": 2},
    }


def test_score_counts_found_missed_and_false_alarms():
    sample = {"expect": {"security": [EXP]}, "forbid": {"max_severity": "medium"}}
    s = score(
        {"issues": [issue(), issue(line=1, severity="high")], "meta": meta()}, sample, "security"
    )
    assert (s["found"], s["missed"]) == (["SQLi"], [])
    assert s["false_alarms"] == ["line 7: critical", "line 1: high"]
    assert s["tokens_out"] == 7


def test_case_sets():
    assert [(s["id"], t) for s, t in cases("smoke", None)] == [
        ("sql-injection", "security"),
        ("buggy", "general"),
        ("clean", "general"),
    ]
    full = cases("full", None)
    assert len(full) == 12
    assert [t for s, t in cases("full", "clean")] == ["general", "security"]
