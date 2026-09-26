"""LLM_MODE=fake: a deterministic stand-in for local UI work — no key, no quota."""

import json

from app.domain.ports import LLMRequest, LLMResponse, TokenUsage

_DEMO_REPORT = {
    "summary": (
        "Demo mode (LLM_MODE=fake): this is a canned answer produced without calling "
        "Gemini, so the UI can be developed and tested without using any quota."
    ),
    "issues": [
        {
            "severity": "info",
            "line": 1,
            "category": "maintainability",
            "description": "Demo finding: run the backend with LLM_MODE=gemini for real results.",
            "suggestion": "Set GOOGLE_API_KEY and LLM_MODE=gemini, then analyze again.",
        }
    ],
    "suggestions": ["This suggestion is part of the demo response."],
    "metrics": {"complexity": "low", "readability": "good", "test_coverage_estimate": "none"},
}


class DemoLLMClient:
    def generate(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema is None:
            return LLMResponse("Demo mode: no investigation.", [], None, TokenUsage(), "stop")
        return LLMResponse(json.dumps(_DEMO_REPORT), [], _DEMO_REPORT, TokenUsage(), "stop")
