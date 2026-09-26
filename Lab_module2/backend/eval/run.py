"""Evaluation harness: runs the REAL agent over the sample corpus and scores it.

Quota-safe by design:
- every case result is stored as soon as it arrives and reused on the next run (0 calls);
- --max-calls caps real requests; cases that would exceed it are "skipped (budget)";
- the daily quota stops the run immediately (resume later, nothing is lost).

    python -m eval.run --set smoke --model gemini-3.5-flash-lite
    python -m eval.run --set full --max-calls 60
    python -m eval.run --set full --publish        # copy results to samples/results/
"""

import argparse
import dataclasses
import json
import shutil
import sys
import tempfile
from pathlib import Path

from app.application.analyze import AnalyzeCode
from app.application.prompts import PromptLibrary
from app.config import get_settings
from app.domain.errors import LLMError, LLMQuotaExceeded
from app.domain.models import AnalysisRequest, AnalysisResult, Severity
from app.infrastructure.gemini_client import GeminiClient
from app.infrastructure.llm_decorators import (
    CircuitBreakerLLMClient,
    PacedLLMClient,
    RetryingLLMClient,
)
from app.infrastructure.sqlite_cache import SqliteAnalysisCache

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
RESULTS = Path(__file__).resolve().parent / "results"
SMOKE = [("sql-injection", "security"), ("buggy", "general"), ("clean", "general")]
TARGETS = {"schema_valid": 1.0, "recall": 0.9}


# ---- scoring -------------------------------------------------------------------


def matches(issue: dict, exp: dict) -> bool:
    return (
        issue["category"] in exp["categories"]
        and any(abs(issue["line"] - line) <= exp["tolerance"] for line in exp["lines"])
        and Severity(issue["severity"]).rank >= Severity(exp["min_severity"]).rank
    )


def score(result: dict, sample: dict, analysis_type: str) -> dict:
    expected = sample.get("expect", {}).get(analysis_type, [])
    found = [e["name"] for e in expected if any(matches(i, e) for i in result["issues"])]
    missed = [e["name"] for e in expected if e["name"] not in found]
    forbid = sample.get("forbid", {})
    false_alarms = []
    if "max_severity" in forbid:
        limit = Severity(forbid["max_severity"]).rank
        false_alarms = [
            f"line {i['line']}: {i['severity']}"
            for i in result["issues"]
            if Severity(i["severity"]).rank > limit
        ]
    meta = result["meta"]
    return {
        "expected": len(expected),
        "found": found,
        "missed": missed,
        "false_alarms": false_alarms,
        "dropped_lines": meta["dropped_issues"],
        "calls": meta["llm_calls"],
        "chunks": meta["chunks"],
        "tool_rounds": meta["tool_rounds"],
        "tokens_in": meta["tokens"]["input"],
        "tokens_out": meta["tokens"]["output"] + meta["tokens"]["thinking"],
    }


# ---- running -------------------------------------------------------------------


def cases(name: str, only: str | None) -> list[tuple[dict, str]]:
    catalog = {s["id"]: s for s in json.loads((SAMPLES / "expected.json").read_text())["samples"]}
    if name == "smoke":
        selected = [(catalog[i], t) for i, t in SMOKE]
    else:
        selected = [(s, t) for s in catalog.values() for t in s["analysis_types"]]
    return [(s, t) for s, t in selected if only is None or s["id"] == only]


def estimated_calls(sample: dict) -> int:
    return 6 if "context_budget_tokens" in sample else 3  # chunks × 2, or investigate+tool+report


def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    model = args.model or settings.gemini_model
    settings = dataclasses.replace(settings, gemini_model=model)
    prompts = PromptLibrary()
    store = RESULTS / model / f"prompt-v{prompts.version}"
    store.mkdir(parents=True, exist_ok=True)

    llm = None
    if settings.google_api_key:
        gemini = GeminiClient(settings.google_api_key, model, settings.llm_timeout_s)
        llm = CircuitBreakerLLMClient(
            RetryingLLMClient(PacedLLMClient(gemini, settings.llm_min_interval_s))
        )

    rows, calls_used, stop_reason = [], 0, None
    for sample, analysis_type in cases(args.set, args.only):
        case = f"{sample['id']}.{analysis_type}"
        path = store / f"{case}.json"
        row = {"case": case, "status": "", "score": None}
        if path.is_file():
            row["status"] = "cached"
        elif stop_reason:
            row["status"] = f"skipped ({stop_reason})"
        elif llm is None:
            row["status"] = "skipped (no GOOGLE_API_KEY)"
        elif calls_used + estimated_calls(sample) > args.max_calls:
            row["status"] = "skipped (budget)"
        else:
            case_settings = dataclasses.replace(
                settings,
                context_budget_tokens=sample.get(
                    "context_budget_tokens", settings.context_budget_tokens
                ),
            )
            with tempfile.TemporaryDirectory() as tmp:
                use_case = AnalyzeCode(
                    llm, SqliteAnalysisCache(f"{tmp}/c.db"), prompts, case_settings
                )
                request = AnalysisRequest(
                    code=(SAMPLES / sample["file"]).read_text(),
                    language=sample["language"],
                    analysis_type=analysis_type,
                )
                try:
                    result: AnalysisResult = use_case(request)
                except LLMQuotaExceeded as err:
                    stop_reason = f"{err.scope} quota"
                    row["status"] = f"stopped ({err})"
                    rows.append(row)
                    print(f"{case:32} STOPPED: {err}", flush=True)
                    continue
                except LLMError as err:
                    row["status"] = f"error: {type(err).__name__}: {err}"
                    rows.append(row)
                    print(f"{case:32} ERROR: {err}", flush=True)
                    continue
            path.write_text(result.model_dump_json(indent=2))
            calls_used += result.meta.llm_calls
            row["status"] = "ran"
        if path.is_file():
            row["score"] = score(json.loads(path.read_text()), sample, analysis_type)
            s = row["score"]
            print(
                f"{case:32} {row['status']:7} found {len(s['found'])}/{s['expected']}"
                f"  missed={s['missed']} false_alarms={s['false_alarms']}"
                f"  calls={s['calls']}",
                flush=True,
            )
        else:
            print(f"{case:32} {row['status']}", flush=True)
        rows.append(row)

    report = write_report(rows, model, prompts.version, calls_used, args.set)
    print(f"\nreal calls this run: {calls_used}  →  {report.relative_to(ROOT)}")
    if stop_reason:
        print("Run stopped early; re-run later to resume (finished cases are kept).")
    if args.publish:
        publish(store)
    return 0


def write_report(rows: list[dict], model: str, version: str, calls: int, set_name: str) -> Path:
    scored = [r for r in rows if r["score"]]
    expected = sum(r["score"]["expected"] for r in scored)
    found = sum(len(r["score"]["found"]) for r in scored)
    recall = found / expected if expected else 0.0
    false_alarms = sum(len(r["score"]["false_alarms"]) for r in scored)
    lines = [
        f"# Evaluation report — `{model}`, prompt v{version}, set `{set_name}`",
        "",
        f"- Cases scored: **{len(scored)}/{len(rows)}**",
        f"- Schema validity: **{len(scored)}/{len(scored)}** (every stored result passed strict "
        "Pydantic validation)",
        f"- Recall of planted issues: **{found}/{expected} = {recall:.0%}** "
        f"(target ≥ {TARGETS['recall']:.0%}) {'✅' if recall >= TARGETS['recall'] else '❌'}",
        f"- False alarms on clean code: **{false_alarms}** {'✅' if false_alarms == 0 else '❌'}",
        f"- Real LLM calls in the last run: **{calls}** (cached cases cost 0)",
        "",
        "| Case | Status | Found | Missed | False alarms | Calls | Chunks | Tool rounds | "
        "Tokens in / out |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["score"]
        if s:
            lines.append(
                f"| {r['case']} | {r['status']} | {len(s['found'])}/{s['expected']} | "
                f"{', '.join(s['missed']) or '—'} | {', '.join(s['false_alarms']) or '—'} | "
                f"{s['calls']} | {s['chunks']} | {s['tool_rounds']} | "
                f"{s['tokens_in']} / {s['tokens_out']} |"
            )
        else:
            lines.append(f"| {r['case']} | {r['status']} | | | | | | | |")
    path = Path(__file__).resolve().parent / f"report_{set_name}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def publish(store: Path) -> None:
    target = SAMPLES / "results"
    target.mkdir(exist_ok=True)
    for f in store.glob("*.json"):
        shutil.copy(f, target / f.name)
    print(f"published {len(list(store.glob('*.json')))} results → samples/results/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--max-calls", type=int, default=30)
    parser.add_argument("--model", help="override GEMINI_MODEL")
    parser.add_argument("--only", help="run a single sample id")
    parser.add_argument("--publish", action="store_true", help="copy results to samples/results")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
