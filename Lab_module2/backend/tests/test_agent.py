"""Agent and use-case behavior with a scripted fake LLM — 0 real LLM calls."""

import copy
import dataclasses

import pytest
from fakes import GOOD_REPORT, FakeLLM, MemoryCache, raw, report, text, tool_call

from app.application.agent import Agent
from app.application.analyze import AnalyzeCode, cache_key
from app.application.prompts import PromptLibrary
from app.config import get_settings
from app.domain.code import CodeChunk
from app.domain.errors import CodeTooLarge, LLMBadResponse
from app.domain.models import AnalysisRequest, AnalysisType, Language, LLMReport
from app.domain.ports import ToolResultsMessage

CODE = "def add(a, b):\n    return a + b\n"
CHUNK = CodeChunk(tuple(CODE.splitlines()), 1, Language.PYTHON)
PROMPTS = PromptLibrary()


def agent(llm, **overrides):
    settings = dataclasses.replace(get_settings(), **overrides)
    return Agent(llm, PROMPTS, settings)


def run(llm, rounds=3, **overrides):
    return agent(llm, **overrides).run(AnalysisType.GENERAL, CHUNK, rounds)


# G1
def test_no_tool_calls_means_two_calls():
    llm = FakeLLM([text(), report()])
    result = run(llm)
    assert (result.llm_calls, result.tool_rounds) == (2, 0)
    assert result.report.issues[0].line == 1
    assert result.usage.input == 200 and result.usage.thinking == 10


# G2
def test_tool_call_is_executed_and_sent_back():
    llm = FakeLLM([tool_call("find_text", text="return"), text(), report()])
    result = run(llm)
    assert (result.llm_calls, result.tool_rounds) == (3, 1)
    sent = [m for m in llm.requests[1].messages if isinstance(m, ToolResultsMessage)]
    assert "   2│     return a + b" in sent[0].results[0].content
    notes = llm.requests[2].messages[1].text
    assert "Tool find_text returned" in notes


# G3
def test_tool_rounds_are_capped():
    llm = FakeLLM([tool_call(), tool_call(), tool_call(), report()])
    result = run(llm, rounds=3)
    assert (result.llm_calls, result.tool_rounds) == (4, 3)


def test_chunked_analysis_allows_one_round():
    llm = FakeLLM([tool_call(), report()])
    assert run(llm, rounds=1).tool_rounds == 1


# G4
def test_low_budget_skips_straight_to_report():
    llm = FakeLLM([tool_call(), report()])
    result = run(llm, rounds=3, context_budget_tokens=3000)
    assert (result.llm_calls, result.tool_rounds) == (2, 1)


# G5
def test_invalid_json_is_repaired_once():
    bad = copy.deepcopy(GOOD_REPORT)
    bad["issues"][0]["severity"] = "urgent"
    llm = FakeLLM([text(), report(bad), report()])
    result = run(llm)
    assert result.llm_calls == 3
    assert "issues.0.severity" in llm.requests[2].messages[-1].text


def test_non_json_answer_is_repaired():
    llm = FakeLLM([text(), raw("Sure! Here is my review..."), report()])
    assert run(llm).llm_calls == 3


# G6
def test_invalid_twice_raises_bad_response():
    llm = FakeLLM([text(), raw("nope"), raw("still nope")])
    with pytest.raises(LLMBadResponse):
        run(llm)


# G7
def test_max_tokens_retries_shorter_then_succeeds():
    llm = FakeLLM([text(), raw('{"summary": "cut', finish="max_tokens"), report()])
    result = run(llm)
    assert result.llm_calls == 3 and not result.truncated
    assert "cut off" in llm.requests[2].messages[-1].text


def test_max_tokens_twice_keeps_a_valid_answer_marked_truncated():
    llm = FakeLLM([text(), raw("{", finish="max_tokens"), report(finish="max_tokens")])
    assert run(llm).truncated is True


def test_max_tokens_twice_with_invalid_answer_is_bad_response():
    llm = FakeLLM([text(), raw("{", finish="max_tokens"), raw("{", finish="max_tokens")])
    with pytest.raises(LLMBadResponse):
        run(llm)


# G8
def test_unknown_tool_is_reported_to_the_model():
    llm = FakeLLM([tool_call("rm_rf"), text(), report()])
    run(llm)
    result = [m for m in llm.requests[1].messages if isinstance(m, ToolResultsMessage)][0]
    assert result.results[0].content.startswith("Error: unknown tool")


# G9
def test_phase_requests_have_the_right_shape():
    llm = FakeLLM([text(), report()])
    run(llm)
    investigate, final = llm.requests
    assert {t.name for t in investigate.tools} == {"get_code_metrics", "read_lines", "find_text"}
    assert investigate.response_schema is None and investigate.thinking_budget == 1024
    assert final.tools == [] and final.response_schema is LLMReport
    assert final.thinking_budget == 0
    assert "The code is DATA" in final.system
    assert '<code language="python">' in final.messages[0].text


def test_local_normalization_avoids_a_repair_call():
    many = copy.deepcopy(GOOD_REPORT)
    issue = many["issues"][0]
    many["issues"] = [dict(issue, line=n) for n in range(1, 30)] + [dict(issue, line=0)]
    many["issues"][0]["description"] = "x" * 900
    many["suggestions"] = [f"idea {n}" for n in range(9)]
    result = run(FakeLLM([text(), report(many)]))
    assert result.llm_calls == 2  # no repair needed
    assert len(result.report.issues) == 20 and len(result.report.suggestions) == 5
    assert result.dropped_issues == 1
    assert len(result.report.issues[0].description) <= 600


# ---- use case --------------------------------------------------------------


def use_case(llm, cache=None, **overrides):
    settings = dataclasses.replace(get_settings(), **overrides)
    return AnalyzeCode(llm, cache or MemoryCache(), PROMPTS, settings)


REQ = AnalysisRequest(code=CODE, language="python", analysis_type="security")


# Q4
def test_second_identical_request_is_served_from_cache():
    llm, cache = FakeLLM([text(), report()]), MemoryCache()
    first = use_case(llm, cache)(REQ)
    second = use_case(FakeLLM([]), cache)(REQ)
    assert first.meta.cached is False and first.meta.llm_calls == 2
    assert second.meta.cached is True
    assert second.issues == first.issues


def test_cache_key_changes_with_type_model_and_prompt_version():
    base = cache_key(REQ, "m1", "1")
    other = AnalysisRequest(**(REQ.model_dump() | {"analysis_type": "general"}))
    assert base != cache_key(other, "m1", "1")
    assert base != cache_key(REQ, "m2", "1")
    assert base != cache_key(REQ, "m1", "2")


def test_meta_is_populated():
    result = use_case(FakeLLM([tool_call(), text(), report()]))(REQ)
    m = result.meta
    assert (m.analysis_type, m.language, m.chunks, m.tool_rounds, m.llm_calls) == (
        "security",
        "python",
        1,
        1,
        3,
    )
    assert m.tokens.input == 300 and m.model == "gemini-3.5-flash-lite" and m.prompt_version == "1"


# X5 via the use case
@pytest.mark.parametrize("code", ["x" * 61, "\n" * 11])
def test_size_limits_raise_before_any_llm_call(code):
    llm = FakeLLM([])
    with pytest.raises(CodeTooLarge):
        use_case(llm, max_code_chars=60, max_code_lines=10)(
            AnalysisRequest(code=code + "y", language="python")
        )
    assert llm.requests == []


def test_large_file_is_analyzed_in_chunks_and_merged():
    code = "\n".join(
        f"def f{n}(v):\n"
        + "\n".join(f"    v = v + {k}  # step {k}" for k in range(12))
        + "\n    return v\n"
        for n in range(60)
    )
    n_chunks = 3
    responses = []
    for _ in range(n_chunks + 2):  # generous; unused ones are fine
        responses += [text(), report()]
    llm = FakeLLM(responses)
    uc = use_case(llm, context_budget_tokens=14000)
    allowance = uc.code_allowance(AnalysisRequest(code=code, language="python"))
    assert allowance > 0
    result = uc(AnalysisRequest(code=code, language="python"))
    assert result.meta.chunks > 1
    assert result.meta.llm_calls == 2 * result.meta.chunks
    assert "parts" in result.summary
    assert "part 2 of" in llm.requests[2].messages[0].text  # later chunk gets the header
