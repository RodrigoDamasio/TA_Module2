import pytest
from pydantic import ValidationError

from app.application.postprocess import clean_issues, merge
from app.domain.models import AnalysisReport, Category, Issue, Metrics, Severity


def issue(line=1, severity="medium", category="bug", description="Something is wrong here"):
    return Issue(
        severity=severity,
        line=line,
        category=category,
        description=description,
        suggestion="Fix it like this.",
    )


def report(issues=(), complexity="low", readability="good", coverage="none", summary=None):
    return AnalysisReport(
        summary=summary or "This code does something reasonable overall.",
        issues=list(issues),
        suggestions=["Add tests."],
        metrics=Metrics(
            complexity=complexity, readability=readability, test_coverage_estimate=coverage
        ),
    )


# D1
@pytest.mark.parametrize(
    "change",
    [
        {"issues": [issue()] * 21},
        {"summary": ""},
        {
            "metrics": {
                "complexity": "huge",
                "readability": "good",
                "test_coverage_estimate": "none",
            }
        },
    ],
)
def test_report_rejects_invalid_values(change):
    data = report().model_dump() | change
    with pytest.raises(ValidationError):
        AnalysisReport.model_validate(data)


@pytest.mark.parametrize(
    "field, value", [("line", 0), ("severity", "urgent"), ("category", "naming")]
)
def test_issue_rejects_invalid_values(field, value):
    data = issue().model_dump() | {field: value}
    with pytest.raises(ValidationError):
        Issue.model_validate(data)


# D2
def test_clean_issues_drops_out_of_range_dedupes_sorts_and_caps():
    issues = [
        issue(line=50),  # beyond the file
        issue(line=3, severity="low"),
        issue(line=3, severity="high"),  # duplicate of the one above, more severe
        issue(line=1, severity="critical", category="security"),
    ] + [issue(line=5, description=f"Distinct problem number {n}") for n in range(25)]

    cleaned, dropped = clean_issues(issues, total_lines=10)

    assert dropped == 1
    assert len(cleaned) == 20
    assert cleaned[0].severity == Severity.CRITICAL
    line3 = [i for i in cleaned if i.line == 3]
    assert len(line3) == 1 and line3[0].severity == Severity.HIGH


# X6
def test_merge_takes_worst_metrics_and_dedupes_across_chunks():
    a = report([issue(line=2, severity="medium")], complexity="low", readability="good")
    b = report(
        [issue(line=2, severity="high"), issue(line=8, category="performance")],
        complexity="high",
        readability="fair",
        coverage="low",
    )

    merged, dropped = merge([a, b], total_lines=10)

    assert dropped == 0
    assert [(i.line, i.severity) for i in merged.issues] == [(2, "high"), (8, "medium")]
    assert merged.metrics.complexity == "high"
    assert merged.metrics.readability == "fair"
    assert merged.metrics.test_coverage_estimate == "none"
    assert "2 parts" in merged.summary
    assert merged.suggestions == ["Add tests."]


def test_severity_ranks_are_ordered():
    assert [s.rank for s in Severity] == [4, 3, 2, 1, 0]
    assert Category("security") is Category.SECURITY
