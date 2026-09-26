"""Named failures. Mapped to RFC 9457 problems only in app.api."""

from typing import Literal


class DomainError(Exception):
    """Base class for every expected failure."""


class CodeTooLarge(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LLMError(DomainError):
    """Base class for failures talking to the LLM provider."""


class LLMQuotaExceeded(LLMError):
    def __init__(self, scope: Literal["minute", "day"], retry_after_s: float) -> None:
        super().__init__(f"LLM quota exceeded ({scope}); retry after {retry_after_s:.0f}s.")
        self.scope = scope
        self.retry_after_s = retry_after_s


class LLMUnavailable(LLMError):
    def __init__(self, reason: str, retry_after_s: float = 10) -> None:
        super().__init__(reason)
        self.retry_after_s = retry_after_s


class LLMTimeout(LLMError):
    pass


class LLMRequestRejected(LLMError):
    """The provider refused the request (bad key, invalid request, blocked content)."""

    def __init__(self, status: int | None, reason: str) -> None:
        super().__init__(reason)
        self.status = status


class LLMBadResponse(LLMError):
    """The model's answer could not be turned into a valid report."""
