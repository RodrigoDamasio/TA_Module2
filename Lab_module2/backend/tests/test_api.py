"""HTTP contract, RFC 9457 problems, guards, samples, CORS — fake LLM, 0 real calls."""

import pytest
from fakes import report, text

from app.domain.errors import (
    LLMBadResponse,
    LLMQuotaExceeded,
    LLMRequestRejected,
    LLMTimeout,
    LLMUnavailable,
)

PROBLEM = "application/problem+json"
ORIGIN = "http://localhost:3000"
BODY = {"code": "def add(a, b):\n    return a + b\n", "language": "python"}


def assert_problem(r, status, slug):
    assert r.status_code == status, r.text
    assert r.headers["content-type"] == PROBLEM
    body = r.json()
    assert body["status"] == status
    assert body["type"] == f"http://test.local/problems/{slug}"
    assert body["title"] and body["instance"] == "/analyze"
    return body


# A1
def test_analyze_returns_a_valid_report(client, llm, good_run):
    llm.responses += good_run
    r = client.post("/analyze", json=BODY | {"analysis_type": "security"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"summary", "issues", "suggestions", "metrics", "meta"}
    assert body["issues"][0]["line"] == 1
    assert body["meta"]["analysis_type"] == "security"
    assert body["meta"]["llm_calls"] == 2 and body["meta"]["cached"] is False


def test_analysis_type_defaults_to_general(client, llm, good_run):
    llm.responses += good_run
    assert client.post("/analyze", json=BODY).json()["meta"]["analysis_type"] == "general"


def test_repeat_request_is_cached_and_free(client, llm, good_run):
    llm.responses += good_run
    client.post("/analyze", json=BODY)
    r = client.post("/analyze", json=BODY)
    assert r.json()["meta"]["cached"] is True
    assert len(llm.requests) == 2  # no new LLM call


# A2 — validation
@pytest.mark.parametrize(
    "body, pointer",
    [
        ({"language": "python"}, "#/code"),
        ({"code": "", "language": "python"}, "#/code"),
        ({"code": "   \n ", "language": "python"}, "#/code"),
        ({"code": "x = 1", "language": "cobol"}, "#/language"),
        ({"code": "x = 1", "language": "python", "analysis_type": "vibes"}, "#/analysis_type"),
    ],
)
def test_invalid_requests_are_validation_problems(client, llm, body, pointer):
    problem = assert_problem(client.post("/analyze", json=body), 422, "validation-error")
    assert [e["pointer"] for e in problem["errors"]] == [pointer]
    assert llm.requests == []


def test_blank_code_message_is_friendly(client):
    r = client.post("/analyze", json={"code": "  ", "language": "python"})
    assert r.json()["errors"][0]["detail"] == "Code must not be blank."


def test_not_json_is_400(client):
    r = client.post("/analyze", content="nope", headers={"Content-Type": "application/json"})
    assert_problem(r, 400, "malformed-request")


# A3
def test_oversized_code_is_413_before_any_llm_call(client, llm, monkeypatch):
    monkeypatch.setenv("MAX_CODE_CHARS", "20")
    problem = assert_problem(client.post("/analyze", json=BODY), 413, "code-too-large")
    assert "maximum is 20" in problem["detail"]
    assert llm.requests == []


# A2 — LLM failures
@pytest.mark.parametrize(
    "error, status, slug, retry_after",
    [
        (LLMQuotaExceeded("minute", 12), 503, "llm-quota-exhausted", "12"),
        (LLMQuotaExceeded("day", 0), 503, "llm-quota-exhausted", "60"),
        (LLMUnavailable("busy", 15), 503, "llm-unavailable", "15"),
        (LLMTimeout("slow"), 504, "llm-timeout", None),
        (LLMRequestRejected(403, "bad key"), 502, "llm-request-rejected", None),
        (LLMBadResponse("garbage"), 502, "llm-bad-response", None),
    ],
)
def test_llm_errors_become_problems(client, llm, error, status, slug, retry_after):
    llm.responses.append(error)
    r = client.post("/analyze", json=BODY, headers={"Origin": ORIGIN})
    assert_problem(r, status, slug)
    assert r.headers.get("retry-after") == retry_after
    assert r.headers["access-control-allow-origin"] == ORIGIN


def test_unexpected_error_is_500_problem_with_cors(client, llm):
    llm.responses.append(RuntimeError("secret internal detail"))
    r = client.post("/analyze", json=BODY, headers={"Origin": ORIGIN})
    assert_problem(r, 500, "internal-error")
    assert "secret internal detail" not in r.text
    assert r.headers["access-control-allow-origin"] == ORIGIN


# Q5
def test_rate_limit_counts_only_cache_misses(client, llm):
    for n in range(5):
        llm.responses += [text(), report()]
        assert client.post("/analyze", json=BODY | {"code": f"x = {n}"}).status_code == 200
    # cache hits are still free
    assert client.post("/analyze", json=BODY | {"code": "x = 0"}).status_code == 200
    r = client.post("/analyze", json=BODY | {"code": "x = 99"}, headers={"Origin": ORIGIN})
    assert_problem(r, 429, "rate-limited")
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()


# A4
def test_samples_list_and_detail_use_no_llm(client, llm):
    samples = client.get("/samples").json()
    ids = {s["id"] for s in samples}
    assert {"sql-injection", "clean", "large-module", "prompt-injection"} <= ids
    detail = client.get("/samples/sql-injection", params={"analysis_type": "security"}).json()
    assert 'f"SELECT id, email' in detail["code"]
    assert detail["language"] == "python"
    assert llm.requests == []


def test_unknown_sample_is_404_about_blank(client):
    r = client.get("/samples/nope")
    assert r.status_code == 404 and r.json()["type"] == "about:blank"


# A5
def test_cors_preflight(client):
    r = client.options(
        "/analyze",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert r.headers["access-control-allow-origin"] == ORIGIN
    evil = client.options(
        "/analyze",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in evil.headers


# A6
def test_health_does_not_call_the_llm(client, llm):
    r = client.get("/health")
    assert r.json() == {"status": "ok", "model": "gemini-3.8-flash", "llm_mode": "gemini"}
    assert llm.requests == []


def test_problem_types_are_documented(client):
    for slug in ("code-too-large", "rate-limited", "llm-quota-exhausted", "llm-timeout"):
        assert client.get(f"/problems/{slug}").status_code == 200


def test_openapi_lists_problem_responses(client):
    responses = client.get("/openapi.json").json()["paths"]["/analyze"]["post"]["responses"]
    assert {"413", "422", "429", "503"} <= set(responses)
