"""The analysis contract. Pydantic is the only third-party import allowed in the domain."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Language(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"


class AnalysisType(StrEnum):
    GENERAL = "general"
    SECURITY = "security"
    PERFORMANCE = "performance"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


class Category(StrEnum):
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    MAINTAINABILITY = "maintainability"


Complexity = Literal["low", "medium", "high"]
Readability = Literal["poor", "fair", "good", "excellent"]
Coverage = Literal["none", "low", "medium", "high"]

MAX_ISSUES = 20
MAX_SUGGESTIONS = 5


# ---- request -----------------------------------------------------------------


class AnalysisRequest(BaseModel):
    code: str = Field(min_length=1, description="Source code to analyze")
    language: Language
    analysis_type: AnalysisType = AnalysisType.GENERAL

    @field_validator("code")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code must not be blank.")
        return value


# ---- strict models: what the API guarantees --------------------------------


class Issue(BaseModel):
    severity: Severity
    line: int = Field(ge=1)
    category: Category
    description: str = Field(min_length=10, max_length=600)
    suggestion: str = Field(min_length=5, max_length=800)


class Metrics(BaseModel):
    complexity: Complexity
    readability: Readability
    test_coverage_estimate: Coverage


class AnalysisReport(BaseModel):
    summary: str = Field(min_length=20, max_length=800)
    issues: list[Issue] = Field(max_length=MAX_ISSUES)
    suggestions: list[str] = Field(max_length=MAX_SUGGESTIONS)
    metrics: Metrics


# ---- lenient twins: the schema sent to the model ----------------------------
# Gemini accepts only a subset of JSON Schema, so the model gets the same fields
# and enums without length/count limits; the strict models above validate locally.


class LLMIssue(BaseModel):
    severity: Severity
    line: int
    category: Category
    description: str
    suggestion: str


class LLMReport(BaseModel):
    summary: str
    issues: list[LLMIssue]
    suggestions: list[str]
    metrics: Metrics


# ---- result returned by the API --------------------------------------------


class TokenCounts(BaseModel):
    input: int = 0
    output: int = 0
    thinking: int = 0


class AnalysisMeta(BaseModel):
    analysis_type: AnalysisType
    language: Language
    model: str
    prompt_version: str
    cached: bool = False
    chunks: int = 1
    tool_rounds: int = 0
    llm_calls: int = 0
    tokens: TokenCounts = TokenCounts()
    truncated: bool = False
    dropped_issues: int = 0


class AnalysisResult(AnalysisReport):
    meta: AnalysisMeta
