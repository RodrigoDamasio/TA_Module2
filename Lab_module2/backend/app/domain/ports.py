"""Provider-neutral abstractions the application depends on."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from .models import AnalysisResult

FinishReason = Literal["stop", "max_tokens", "safety", "other"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    id: str | None
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str | None
    name: str
    content: str


@dataclass(frozen=True)
class TokenUsage:
    input: int = 0
    output: int = 0
    thinking: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            self.input + other.input, self.output + other.output, self.thinking + other.thinking
        )


# ---- conversation messages ---------------------------------------------------


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    text: str | None
    tool_calls: list[ToolCall]
    raw_turn: Any = None  # provider turn, echoed back unchanged in the next request


@dataclass(frozen=True)
class ToolResultsMessage:
    results: list[ToolResult]


Message = UserMessage | AssistantMessage | ToolResultsMessage


@dataclass(frozen=True)
class LLMRequest:
    system: str
    messages: list[Message]
    tools: list[ToolSpec] = field(default_factory=list)
    response_schema: type[BaseModel] | None = None
    max_output_tokens: int = 2048
    thinking_budget: int | None = None


@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    parsed: dict[str, Any] | None
    usage: TokenUsage
    finish_reason: FinishReason
    raw_turn: Any = None

    def as_message(self) -> AssistantMessage:
        return AssistantMessage(self.text, self.tool_calls, self.raw_turn)


class LLMClient(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...


class AnalysisCache(Protocol):
    def get(self, key: str) -> AnalysisResult | None: ...

    def put(self, key: str, result: AnalysisResult) -> None: ...
