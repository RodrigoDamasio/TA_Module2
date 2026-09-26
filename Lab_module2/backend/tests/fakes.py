"""Test doubles: a scripted LLM and an in-memory cache. No network, no quota."""

import json
from collections.abc import Iterable

from app.domain.errors import LLMError
from app.domain.models import AnalysisResult
from app.domain.ports import LLMRequest, LLMResponse, TokenUsage, ToolCall

GOOD_REPORT = {
    "summary": "Adds two numbers and returns the result; small and readable.",
    "issues": [
        {
            "severity": "medium",
            "line": 1,
            "category": "maintainability",
            "description": "The function has no type hints, so callers can pass anything.",
            "suggestion": "def add(a: int, b: int) -> int:",
        }
    ],
    "suggestions": ["Add a unit test for negative numbers."],
    "metrics": {"complexity": "low", "readability": "good", "test_coverage_estimate": "none"},
}

USAGE = TokenUsage(input=100, output=20, thinking=5)


def text(t: str = "Candidate: line 1 lacks type hints.") -> LLMResponse:
    return LLMResponse(t, [], None, USAGE, "stop")


def tool_call(name: str = "get_code_metrics", **args) -> LLMResponse:
    return LLMResponse(None, [ToolCall("c1", name, args)], None, USAGE, "stop")


def report(data: dict | None = None, finish: str = "stop") -> LLMResponse:
    data = GOOD_REPORT if data is None else data
    return LLMResponse(json.dumps(data), [], data, USAGE, finish)


def raw(text_: str, finish: str = "stop") -> LLMResponse:
    return LLMResponse(text_, [], None, USAGE, finish)


class FakeLLM:
    """Returns scripted responses in order and records every request."""

    def __init__(self, responses: Iterable[LLMResponse | LLMError]) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("FakeLLM: no scripted response left")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class MemoryCache:
    def __init__(self) -> None:
        self.data: dict[str, AnalysisResult] = {}

    def get(self, key: str) -> AnalysisResult | None:
        return self.data.get(key)

    def put(self, key: str, result: AnalysisResult) -> None:
        self.data[key] = result
