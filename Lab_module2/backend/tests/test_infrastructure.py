"""Quota wrappers, cache, Gemini adapter mapping (no network), demo client."""

import json
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fakes import GOOD_REPORT, FakeLLM, report
from google.genai import errors, types

from app.domain.errors import (
    LLMOverloaded,
    LLMQuotaExceeded,
    LLMRequestRejected,
    LLMUnavailable,
)
from app.domain.models import (
    AnalysisMeta,
    AnalysisReport,
    AnalysisResult,
    LLMReport,
)
from app.domain.ports import (
    AssistantMessage,
    LLMRequest,
    ToolResult,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from app.infrastructure.demo_llm import DemoLLMClient
from app.infrastructure.gemini_client import (
    build_config,
    quota_error,
    seconds_until_daily_reset,
    thinking_config,
    to_contents,
    to_response,
)
from app.infrastructure.llm_decorators import (
    CircuitBreakerLLMClient,
    ConcurrencyLimitedLLMClient,
    PacedLLMClient,
    RetryingLLMClient,
)
from app.infrastructure.sqlite_cache import SqliteAnalysisCache

REQ = LLMRequest(system="sys", messages=[UserMessage("hi")])


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


# Q1
def test_paced_client_spaces_calls():
    clock = FakeClock()
    paced = PacedLLMClient(FakeLLM([report(), report(), report()]), 6, clock, clock.sleep)
    paced.generate(REQ)
    paced.generate(REQ)
    clock.now += 10
    paced.generate(REQ)
    assert clock.slept == [6]


# Q2
def test_retry_only_short_minute_quota_errors():
    clock = FakeClock()
    inner = FakeLLM([LLMQuotaExceeded("minute", 5), LLMQuotaExceeded("minute", 5), report()])
    assert RetryingLLMClient(inner, sleep=clock.sleep).generate(REQ).finish_reason == "stop"
    assert clock.slept == [5.5, 5.5]

    for error in (LLMQuotaExceeded("day", 5), LLMQuotaExceeded("minute", 120)):
        inner = FakeLLM([error, report()])
        with pytest.raises(LLMQuotaExceeded):
            RetryingLLMClient(inner, sleep=clock.sleep).generate(REQ)
        assert len(inner.requests) == 1  # not retried

    inner = FakeLLM([LLMQuotaExceeded("minute", 1)] * 3)
    with pytest.raises(LLMQuotaExceeded):
        RetryingLLMClient(inner, max_retries=2, sleep=clock.sleep).generate(REQ)
    assert len(inner.requests) == 3


def test_retry_brief_provider_overloads_with_backoff():
    clock = FakeClock()
    inner = FakeLLM([LLMOverloaded("503"), report()])
    assert RetryingLLMClient(inner, sleep=clock.sleep).generate(REQ).finish_reason == "stop"
    assert clock.slept == [5.0]
    inner = FakeLLM([LLMOverloaded("503")] * 3)
    with pytest.raises(LLMOverloaded):
        RetryingLLMClient(inner, sleep=clock.sleep).generate(REQ)
    assert len(inner.requests) == 3
    busy = FakeLLM([LLMUnavailable("queue full"), report()])  # our own "busy" is not retried
    with pytest.raises(LLMUnavailable):
        RetryingLLMClient(busy, sleep=clock.sleep).generate(REQ)


# Q3
def test_circuit_breaker_fails_fast_after_daily_quota():
    clock = FakeClock()
    inner = FakeLLM([LLMQuotaExceeded("day", 300), report()])
    breaker = CircuitBreakerLLMClient(inner, clock)
    with pytest.raises(LLMQuotaExceeded):
        breaker.generate(REQ)
    with pytest.raises(LLMQuotaExceeded) as err:
        breaker.generate(REQ)
    assert len(inner.requests) == 1 and err.value.retry_after_s == 300
    clock.now += 301
    assert breaker.generate(REQ).finish_reason == "stop"


def test_concurrency_limit_rejects_when_busy():
    gate = threading.Event()

    class Slow:
        def generate(self, request):
            gate.wait(2)
            return report()

    limited = ConcurrencyLimitedLLMClient(Slow(), limit=1, wait_s=0.05)
    worker = threading.Thread(target=limited.generate, args=(REQ,))
    worker.start()
    with pytest.raises(LLMUnavailable):
        limited.generate(REQ)
    gate.set()
    worker.join()


# Q4 (storage)
def test_sqlite_cache_round_trip(tmp_path):
    cache = SqliteAnalysisCache(str(tmp_path / "sub" / "c.db"))
    result = AnalysisResult(
        **AnalysisReport.model_validate(GOOD_REPORT).model_dump(),
        meta=AnalysisMeta(
            analysis_type="general", language="python", model="m", prompt_version="1"
        ),
    )
    assert cache.get("k") is None
    cache.put("k", result)
    cache.put("k", result)  # replace is fine
    assert cache.get("k") == result
    assert cache.get("' OR '1'='1") is None  # key is a bound parameter


# ---- Gemini adapter mapping (M1–M6) -------------------------------------------


def _response(parts, finish="STOP", usage=(120, 30, 12)) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=usage[0],
            candidates_token_count=usage[1],
            thoughts_token_count=usage[2],
        ),
    )


# M1
def test_request_mapping_investigate_and_report():
    spec = ToolSpec("find_text", "desc", {"type": "object", "properties": {}})
    investigate = build_config(
        "gemini-2.5-flash",
        LLMRequest("sys", [], tools=[spec], max_output_tokens=1500, thinking_budget=1024),
    )
    assert investigate.system_instruction == "sys"
    assert investigate.automatic_function_calling.disable is True
    assert investigate.tools[0].function_declarations[0].name == "find_text"
    assert investigate.response_schema is None
    assert investigate.thinking_config.thinking_budget == 1024

    final = build_config(
        "gemini-2.5-flash",
        LLMRequest("sys", [], response_schema=LLMReport, max_output_tokens=4000, thinking_budget=0),
    )
    assert final.tools is None and final.response_schema is LLMReport
    assert final.response_mime_type == "application/json"
    assert final.thinking_config.thinking_budget == 0 and final.max_output_tokens == 4000


def test_thinking_config_per_model_family():
    assert thinking_config("gemini-2.5-pro", 0).thinking_budget == 128
    assert thinking_config("gemini-3.5-flash", 0).thinking_level == types.ThinkingLevel.LOW
    assert thinking_config("gemini-3.8-flash", 1024).thinking_level == types.ThinkingLevel.LOW
    assert thinking_config("gemini-3.5-flash", 4096).thinking_level == types.ThinkingLevel.HIGH
    assert thinking_config("gemini-2.5-flash", None) is None


def test_messages_map_to_gemini_contents():
    raw_turn = types.Content(role="model", parts=[types.Part(text="kept as-is")])
    contents = to_contents(
        [
            UserMessage("task"),
            AssistantMessage(None, [], raw_turn),
            ToolResultsMessage([ToolResult("1", "find_text", "  3│ x")]),
            AssistantMessage("notes", []),
        ]
    )
    assert [c.role for c in contents] == ["user", "model", "user", "model"]
    assert contents[1] is raw_turn
    assert contents[2].parts[0].function_response.name == "find_text"
    assert contents[2].parts[0].function_response.response == {"result": "  3│ x"}
    assert contents[3].parts[0].text == "notes"


# M2
def test_tool_call_response():
    r = to_response(
        _response(
            [
                types.Part(
                    function_call=types.FunctionCall(name="read_lines", args={"start": 1, "end": 5})
                )
            ]
        )
    )
    assert [(c.name, c.args) for c in r.tool_calls] == [("read_lines", {"start": 1, "end": 5})]
    assert r.raw_turn.role == "model"


# M3
def test_json_response_and_usage():
    r = to_response(
        _response(
            [
                types.Part(text="thinking...", thought=True),
                types.Part(text=json.dumps(GOOD_REPORT)),
            ]
        )
    )
    assert r.text == json.dumps(GOOD_REPORT)  # thoughts excluded
    assert (r.usage.input, r.usage.output, r.usage.thinking) == (120, 30, 12)
    assert r.finish_reason == "stop"


# M4
def test_max_tokens_finish():
    assert (
        to_response(_response([types.Part(text="{")], "MAX_TOKENS")).finish_reason == "max_tokens"
    )


def test_blocked_answers_are_rejections():
    with pytest.raises(LLMRequestRejected):
        to_response(_response([], "SAFETY"))
    with pytest.raises(LLMRequestRejected):
        to_response(types.GenerateContentResponse(candidates=[]))


# M5
def _quota_body(quota_id, delay="17s"):
    return {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "quota",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
            ],
        }
    }


NOON_PT = datetime(2026, 9, 25, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


@pytest.mark.parametrize(
    "body, scope, retry",
    [
        (_quota_body("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"), "minute", 17),
        # real body seen from gemini-3.8-flash: daily limit with a misleading 12s retryDelay
        (_quota_body("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "12s"), "day", 43200),
        (_quota_body("SomethingNew", "5s"), "day", 43200),  # unknown → safe choice
        ({"error": {"code": 429, "message": "quota"}}, "day", 43200),
    ],
)
def test_quota_errors_are_parsed(body, scope, retry):
    err = quota_error(errors.ClientError(429, body), now=NOON_PT)
    assert (err.scope, err.retry_after_s) == (scope, retry)


def test_daily_reset_is_midnight_pacific():
    assert seconds_until_daily_reset(NOON_PT) == 12 * 3600
    late = NOON_PT.replace(hour=23, minute=59)
    assert seconds_until_daily_reset(late) == 60


def test_demo_client_needs_no_key():
    demo = DemoLLMClient()
    assert demo.generate(REQ).tool_calls == []
    parsed = demo.generate(LLMRequest("s", [], response_schema=LLMReport)).parsed
    assert AnalysisReport.model_validate(parsed).issues[0].severity == "info"


# ---- replay of real Gemini responses recorded by eval/record_cassettes.py ------

CASSETTES = sorted((__import__("pathlib").Path(__file__).parent / "cassettes").glob("*.json"))


def _cassette(n: int) -> types.GenerateContentResponse:
    return types.GenerateContentResponse.model_validate(json.loads(CASSETTES[n].read_text()))


def test_real_tool_call_response_maps():
    r = to_response(_cassette(0))
    assert [c.name for c in r.tool_calls] == ["get_code_metrics"]
    assert r.usage.input > 0 and r.raw_turn.role == "model"


def test_real_investigation_text_maps():
    r = to_response(_cassette(1))
    assert r.tool_calls == [] and "Line 7" in r.text and r.finish_reason == "stop"


def test_real_report_validates_against_the_strict_schema():
    r = to_response(_cassette(2))
    report = AnalysisReport.model_validate(json.loads(r.text))
    assert any(i.line == 7 and i.category == "security" for i in report.issues)


def test_unusable_parsed_model_falls_back_to_text():
    class Unusable(__import__("pydantic").BaseModel):
        def model_dump(self, *args, **kwargs):
            raise RuntimeError("cannot serialize")

    raw = _cassette(2)
    raw.parsed = Unusable()
    r = to_response(raw)
    assert r.parsed is None and json.loads(r.text)["issues"]
