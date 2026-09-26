"""Semantic checks on model output and merging of per-chunk results."""

import re

from app.domain.models import (
    MAX_ISSUES,
    MAX_SUGGESTIONS,
    AnalysisReport,
    Issue,
    Metrics,
)

_COMPLEXITY = ["low", "medium", "high"]  # worse → later
_READABILITY = ["excellent", "good", "fair", "poor"]
_COVERAGE = ["high", "medium", "low", "none"]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()[:40]


def clean_issues(issues: list[Issue], total_lines: int) -> tuple[list[Issue], int]:
    """Drop out-of-range lines, dedupe (keep the most severe), sort, cap."""
    in_range = [i for i in issues if 1 <= i.line <= total_lines]
    dropped = len(issues) - len(in_range)
    best: dict[tuple, Issue] = {}
    for issue in in_range:
        key = (issue.line, issue.category, _norm(issue.description))
        if key not in best or issue.severity.rank > best[key].severity.rank:
            best[key] = issue
    ordered = sorted(best.values(), key=lambda i: (-i.severity.rank, i.line))
    return ordered[:MAX_ISSUES], dropped


def _worst(values: list[str], order: list[str]) -> str:
    return max(values, key=order.index)


def merge(reports: list[AnalysisReport], total_lines: int) -> tuple[AnalysisReport, int]:
    issues, dropped = clean_issues([i for r in reports for i in r.issues], total_lines)
    suggestions: list[str] = []
    for s in (s for r in reports for s in r.suggestions):
        if _norm(s) not in {_norm(x) for x in suggestions}:
            suggestions.append(s)
    summary = reports[0].summary
    if len(reports) > 1:
        note = f" (Large file analyzed in {len(reports)} parts.)"
        summary = summary[: 800 - len(note)] + note
    metrics = Metrics(
        complexity=_worst([r.metrics.complexity for r in reports], _COMPLEXITY),
        readability=_worst([r.metrics.readability for r in reports], _READABILITY),
        test_coverage_estimate=_worst(
            [r.metrics.test_coverage_estimate for r in reports], _COVERAGE
        ),
    )
    report = AnalysisReport(
        summary=summary,
        issues=issues,
        suggestions=suggestions[:MAX_SUGGESTIONS],
        metrics=metrics,
    )
    return report, dropped
