# Backend Plan — Code Analyzer API

Detailed backend design for [PLAN.md](PLAN.md) (big picture) and [Lab2_Code_Analyzer.md](Lab2_Code_Analyzer.md) (assignment): implementation, code sketches, quality strategy, and deployment to Railway.

Library APIs used below were checked against the installed versions: **`google-genai` 2.25.0** and **`lizard` 1.24.0**.

## 1. Scope

| Lab requirement | How the backend meets it |
|---|---|
| `POST /analyze` accepting `{"code", "language"}` | FastAPI route; `analysis_type` is an optional extra field (default `general`) |
| System prompt that instructs the LLM | Versioned prompt library ([PLAN §5](PLAN.md#5-agent-prompt-design)) assembled per analysis type and language |
| Structured JSON: summary, issues (severity, line, category, description, suggestion), suggestions, metrics | Pydantic `AnalysisReport`; Gemini is asked for schema-constrained JSON, then validated strictly |
| Pydantic validation | Request, LLM output, and response models |
| LLM client abstraction (≥ 1 provider) | `LLMClient` port + `GeminiClient` adapter (plus fake/replay adapters for tests) |
| Health check | `GET /health` |
| ≥ 2 analysis types | `general`, `security`, `performance` |
| Agent with tool-use (learning goal) | Two-phase agent: *investigate* with 3 local tools → *report* |
| Tested with sample code | Sample corpus + evaluation harness |
| Deployed | Railway, same pattern as Lab 1 (§14) |

## 2. Stack

| Package | Use |
|---|---|
| `fastapi`, `uvicorn` | API server (same as Lab 1) |
| `pydantic` | Request/response/LLM-output models |
| `google-genai` | Official Gemini SDK (sync client) |
| `lizard` | Per-function cyclomatic complexity and line ranges for Python, JS, TS, Java, Go — used by the metrics tool **and** by the chunker |
| *dev:* `pytest`, `pytest-cov`, `httpx`, `ruff` | Tests, coverage, lint (incl. `S` security rules) |

## 3. Structure

Same layering as the Lab 1 backend (`api → application → domain ← infrastructure`, enforced by architecture tests).

```
backend/
├── app/
│   ├── domain/
│   │   ├── models.py          # Language, AnalysisType, Severity, Category, Issue, Metrics, AnalysisReport
│   │   ├── errors.py          # CodeTooLarge, LLMQuotaExceeded, LLMBadResponse, LLMTimeout, ...
│   │   └── ports.py           # LLMClient, AnalysisCache, Clock (Protocols) + LLM message types
│   ├── application/
│   │   ├── analyze.py         # AnalyzeCode use case: cache → plan chunks → agent → merge → cache
│   │   ├── agent.py           # two-phase agent loop (investigate → report)
│   │   ├── context.py         # token estimate, budget, numbering, chunker, merger
│   │   ├── postprocess.py     # semantic checks: line range, dedupe, caps
│   │   └── prompts.py         # load + assemble prompt files
│   ├── tools/
│   │   ├── registry.py        # tool specs (JSON schema) + dispatch + result trimming
│   │   ├── metrics.py         # get_code_metrics (lizard)
│   │   └── lines.py           # read_lines, find_text
│   ├── prompts/               # prompt library (PLAN §5.1) — plain files, PROMPT_VERSION inside
│   ├── infrastructure/
│   │   ├── gemini_client.py   # GeminiClient adapter (google-genai)
│   │   ├── llm_decorators.py  # PacedLLMClient, RetryingLLMClient (wrap any LLMClient)
│   │   ├── recording.py       # RecordingLLMClient / ReplayLLMClient (cassettes)
│   │   ├── sqlite_cache.py    # SqliteAnalysisCache — the only SQL
│   │   └── database.py
│   ├── api/
│   │   ├── routes.py  schemas.py  problems.py  guards.py  dependencies.py
│   ├── config.py
│   └── main.py                # composition root
├── samples/                   # corpus + expected.json + stored demo results
├── eval/                      # evaluation harness (not deployed)
├── tests/
│   ├── fakes.py  cassettes/   # fake LLM, recorded Gemini responses
│   └── test_*.py
├── requirements.txt  requirements-dev.txt  pyproject.toml  .python-version
├── railpack.json  railway.json  .railwayignore
├── README.md  DEPLOY.md
```

**Design decision — Pydantic in the domain.** Lab 1 kept the domain stdlib-only. Here the analysis report *is* a validation contract (the lab explicitly requires Pydantic), and duplicating it as dataclasses + mappers would add code without benefit. So `domain/` may import **`pydantic` only**; `fastapi`, `google.genai`, `sqlite3`, `lizard` stay out (architecture test).

## 4. Configuration

All settings from environment variables with safe local defaults (`app/config.py`, read via `Depends(get_settings)` like Lab 1).

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — (required for real calls) | Gemini key. Never logged, never returned |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Pinned model (part of the cache key) |
| `LLM_MODE` | `gemini` | `gemini` · `replay` (tests) · `fake` (local UI work without quota) |
| `LLM_MIN_INTERVAL_S` | `6` | Pacing between Gemini calls (set from the AI Studio limits) |
| `LLM_TIMEOUT_S` | `60` | Per-call timeout |
| `CONTEXT_BUDGET_TOKENS` | `16000` | Per-request budget (PLAN §7) |
| `OUTPUT_RESERVE_TOKENS` | `4000` | `max_output_tokens` for the report phase (includes thinking) |
| `THINKING_BUDGET` | `1024` | Thinking tokens for the investigate phase (`0` in the report phase) |
| `MAX_TOOL_ROUNDS` | `3` | Tool rounds per analysis (1 per chunk when chunked) |
| `MAX_CHUNKS` | `4` | Above this → `413` |
| `MAX_CODE_CHARS` / `MAX_CODE_LINES` | `60000` / `2000` | Hard input limits → `413` |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_PER_DAY` | `5` / `50` | Per client IP (only cache misses count) |
| `DATABASE_PATH` | `analyzer.db` | SQLite cache (Railway: `/data/analyzer.db`) |
| `BASE_URL` / `FRONTEND_ORIGIN` | `http://localhost:8000` / `http://localhost:3000` | Problem `type` URIs / CORS (as Lab 1) |

## 5. Domain model

```python
# app/domain/models.py
from enum import StrEnum
from pydantic import BaseModel, Field

class Language(StrEnum):
    PYTHON = "python"; JAVASCRIPT = "javascript"; TYPESCRIPT = "typescript"; JAVA = "java"; GO = "go"

class AnalysisType(StrEnum):
    GENERAL = "general"; SECURITY = "security"; PERFORMANCE = "performance"

class Severity(StrEnum):
    CRITICAL = "critical"; HIGH = "high"; MEDIUM = "medium"; LOW = "low"; INFO = "info"

class Category(StrEnum):
    BUG = "bug"; SECURITY = "security"; PERFORMANCE = "performance"; STYLE = "style"
    MAINTAINABILITY = "maintainability"

class Issue(BaseModel):
    severity: Severity
    line: int = Field(ge=1)
    category: Category
    description: str = Field(min_length=10, max_length=600)
    suggestion: str = Field(min_length=5, max_length=800)

class Metrics(BaseModel):
    complexity: Literal["low", "medium", "high"]
    readability: Literal["poor", "fair", "good", "excellent"]
    test_coverage_estimate: Literal["none", "low", "medium", "high"]

class AnalysisReport(BaseModel):
    summary: str = Field(min_length=20, max_length=800)
    issues: list[Issue] = Field(max_length=20)
    suggestions: list[str] = Field(max_length=5)
    metrics: Metrics
```

- **Two schemas on purpose.** Gemini accepts only a subset of JSON Schema for `response_schema`, so the model is sent a **lenient twin** (same fields and enums, no length/count constraints — `LLMReport`); the strict `AnalysisReport` above validates the result locally. Violations → one repair call (§10).
- `line` is checked against the file length in post-processing (it depends on the input, not the schema).

## 6. LLM abstraction

Provider-neutral port — nothing outside `infrastructure/` knows about `google.genai`.

```python
# app/domain/ports.py (types abridged)
@dataclass(frozen=True)
class ToolSpec:  name: str; description: str; parameters: dict          # JSON Schema
@dataclass(frozen=True)
class ToolCall:  id: str; name: str; args: dict
@dataclass(frozen=True)
class TokenUsage: input: int; output: int; thinking: int = 0

@dataclass(frozen=True)
class LLMRequest:
    system: str
    messages: list[Message]                 # user text / assistant turn / tool results
    tools: list[ToolSpec] = ()              # investigate phase
    response_schema: type[BaseModel] | None = None   # report phase
    max_output_tokens: int = 2048
    thinking_budget: int | None = None

@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    parsed: dict | None                     # JSON object when response_schema was set
    usage: TokenUsage
    finish_reason: Literal["stop", "max_tokens", "safety", "other"]
    raw_turn: object                        # provider turn, echoed back unchanged next round

class LLMClient(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...
```

### 6.1 Gemini adapter

```python
# app/infrastructure/gemini_client.py (sketch)
from google import genai
from google.genai import errors, types

class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_s: int) -> None:
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_s * 1000)
        )
        self._model = model

    def generate(self, req: LLMRequest) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=req.system,
            max_output_tokens=req.max_output_tokens,
            temperature=0.2,                       # reviews should be stable, not creative
            # We run the tool loop ourselves (budget, trimming, round caps):
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description,
                                          parameters_json_schema=t.parameters)
                for t in req.tools])] if req.tools else None,
            response_mime_type="application/json" if req.response_schema else None,
            response_schema=req.response_schema,
            thinking_config=(types.ThinkingConfig(thinking_budget=req.thinking_budget)
                             if req.thinking_budget is not None else None),
        )
        try:
            r = self._client.models.generate_content(
                model=self._model, contents=_to_contents(req.messages), config=config)
        except errors.ClientError as e:
            if e.code == 429:
                raise _quota_error(e) from e       # LLMQuotaExceeded(scope, retry_after_s)
            raise LLMRequestRejected(e.code) from e
        except errors.ServerError as e:
            raise LLMUnavailable(e.code) from e
        # timeouts from the HTTP layer → LLMTimeout
        return _to_response(r)                     # usage_metadata, function_calls, parsed, finish_reason
```

- **Quota errors:** a `429` carries `details["error"]["details"]`: a `RetryInfo.retryDelay` (e.g. `"17s"`) and a `QuotaFailure` whose quota id names the window (per-minute vs per-day). `_quota_error` maps this to `LLMQuotaExceeded(scope="minute"|"day", retry_after_s)`; unknown → treated as `"day"` (the safe choice: stop).
- **Token usage:** `usage_metadata.prompt_token_count`, `candidates_token_count`, `thoughts_token_count` → `TokenUsage` → `meta.tokens`.
- **Thinking:** Gemini 2.5 uses `thinking_budget`; Gemini 3.x models use `thinking_level` — the adapter picks the right field per model family.

### 6.2 Decorators (open/closed — wrap any client)

| Decorator | Behavior |
|---|---|
| `PacedLLMClient` | Waits so consecutive calls are ≥ `LLM_MIN_INTERVAL_S` apart (thread-safe) |
| `RetryingLLMClient` | On `LLMQuotaExceeded(scope="minute")` with a short `retry_after` (≤ 30 s): sleep and retry, at most 2 times. `scope="day"` or long delays: re-raise immediately |
| `RecordingLLMClient` / `ReplayLLMClient` | Save / replay `(request fingerprint → response)` as JSON cassettes in `tests/cassettes/` |

Production wiring: `Retrying(Paced(GeminiClient))`.

## 7. The agent

### 7.1 Use case

```python
# app/application/analyze.py (sketch)
class AnalyzeCode:
    def __call__(self, req: AnalysisRequest) -> AnalysisResult:
        key = cache_key(req.code, req.language, req.analysis_type, self.model, PROMPT_VERSION)
        if hit := self.cache.get(key):
            return hit.with_meta(cached=True)

        chunks = self.context.plan(req.code, req.language)      # 1..MAX_CHUNKS or CodeTooLarge
        max_rounds = self.max_tool_rounds if len(chunks) == 1 else 1
        partials = [self.agent.run(req, chunk, max_rounds) for chunk in chunks]
        result = merge(partials, total_lines=count_lines(req.code))
        result = postprocess(result, total_lines=...)            # range check, dedupe, caps
        self.cache.put(key, result)
        return result
```

### 7.2 Two-phase loop

```python
# app/application/agent.py (sketch)
def run(self, req, chunk, max_rounds) -> PartialResult:
    system = self.prompts.system(req.analysis_type, req.language)
    messages = [user(self.prompts.investigate(req, chunk, max_rounds))]
    budget = self.context.budget(system, messages)

    # Phase 1 — investigate (chain-of-thought + tools)
    for _ in range(max_rounds):
        if budget.remaining < budget.reserve_for_report:
            break                                               # finalize-when-low
        r = self.llm.generate(LLMRequest(system, messages, tools=TOOL_SPECS,
                                         max_output_tokens=1500, thinking_budget=THINKING))
        messages.append(assistant(r))
        budget.spend(r.usage)
        if not r.tool_calls:
            break                                               # model finished investigating
        results = [self.tools.run(call, chunk) for call in r.tool_calls]   # trimmed
        messages.append(tool_results(results))

    # Phase 2 — report (schema-constrained, no tools)
    messages.append(user(self.prompts.report(req)))
    r = self.llm.generate(LLMRequest(system, messages, response_schema=LLMReport,
                                     max_output_tokens=OUTPUT_RESERVE, thinking_budget=0))
    report = self.validate_or_repair(r, system, messages)       # ≤ 1 repair call
    return PartialResult(report, usage=..., llm_calls=..., tool_rounds=...)
```

**LLM calls per analysis:** 1 (no tools used) to `max_rounds + 1`, plus at most 1 repair. Typical: 2.

## 8. Tools

Deterministic, local, bounded. Tools see only the current chunk's lines (with original numbering).

| Tool | Parameters | Returns (trimmed to ≤ 2,000 chars) |
|---|---|---|
| `get_code_metrics` | — | Lines of code, number of functions, per-function cyclomatic complexity with line ranges (lizard), max/avg complexity, a `complexity` hint (low ≤ 5, medium ≤ 10, high > 10 max CCN) |
| `read_lines` | `start: int`, `end: int` (≤ 60 lines) | Numbered lines `start..end`, clamped to the chunk |
| `find_text` | `text: str` (1–80 chars) | Up to 20 matching line numbers with the line content — **plain case-insensitive substring**, no regex (avoids ReDoS from model-supplied patterns) |

Unknown tool names or invalid arguments return an error *message to the model* (not an exception), so the loop continues.

## 9. Context management

| Piece | Implementation |
|---|---|
| **Estimate** | `ceil(chars / 3)` for code and prompts (conservative; Module 1 measured ~3.1 chars/token for code). Numbered-line prefix (`1234│ `) is included in `chars` |
| **Budget** | `CONTEXT_BUDGET_TOKENS` = system (measured) + code + tool traffic + `OUTPUT_RESERVE_TOKENS`. The code allowance per request is what remains after the fixed parts |
| **Chunker** | If numbered code exceeds the code allowance: split at **function/class boundaries from lizard** (all 5 languages), packing consecutive functions until the allowance is reached; top-level code between functions stays with the following function; a single function larger than the allowance is split at blank lines. `> MAX_CHUNKS` → `CodeTooLarge` (413) |
| **Chunk header** | File outline (function names + line ranges, from lizard) and import lines (per-language prefixes: `import`/`from`, `require(`, `package`) — see `chunk_header.md` |
| **Merge** | Issues keep original line numbers (chunks carry them); dedupe by `(line, category, normalized description prefix)`; keep highest severity; metrics = worst complexity, lowest readability, lowest coverage estimate; summary = model summary of the first chunk + "analyzed in N parts" note (no extra LLM call) |
| **Truncation** | `finish_reason == "max_tokens"` in the report phase → one retry asking for ≤ 10 issues; still truncated → keep the parsed prefix if valid and set `meta.truncated = true`, else `502 llm-bad-response` |

## 10. Validation and post-processing

1. Parse `response.parsed` (or `text`) → `LLMReport` (lenient).
2. Validate → `AnalysisReport` (strict). On failure: **one** repair call with `repair.md` + the Pydantic errors. Still invalid → `LLMBadResponse` (502).
3. Semantic checks: drop issues whose `line` > total lines (counted in `meta.dropped_issues`); dedupe; sort by severity then line; cap at 20.

## 11. API

| Method · Path | Description | LLM calls |
|---|---|---|
| `POST /analyze` | Analyze code; body `{code, language, analysis_type?}` | 0 (cache hit) to ~2 per chunk |
| `GET /samples` | List samples (`id`, `title`, `language`, `analysis_types`) | 0 |
| `GET /samples/{id}?analysis_type=` | Sample code + its stored result (generated by the evaluation, committed in `samples/results/`) | 0 |
| `GET /health` | `{"status": "ok", "model": "...", "llm_mode": "gemini"}` — no LLM call | 0 |
| `GET /problems/{slug}` | Problem type docs (RFC 9457) | 0 |

**Request validation:** `code` 1..`MAX_CODE_CHARS` chars and ≤ `MAX_CODE_LINES` lines, not blank; `language` ∈ enum; `analysis_type` ∈ enum (default `general`). Size limits are checked **before** anything else → `413 code-too-large` (not 422), so the frontend can show the limit.

**Response:** `AnalysisReport` + `meta` (PLAN §6), with `meta.llm_calls`, `meta.tokens`, `meta.chunks`, `meta.tool_rounds`, `meta.cached`, `meta.truncated`, `meta.dropped_issues`.

**Errors (RFC 9457, reusing Lab 1's `problems.py`):**

| Domain error | HTTP | Problem slug | Headers |
|---|---|---|---|
| request body not JSON | 400 | `malformed-request` | |
| `CodeTooLarge` | 413 | `code-too-large` | |
| Pydantic request errors | 422 | `validation-error` (+ `errors[]` pointers) | |
| per-client limit | 429 | `rate-limited` | `Retry-After` |
| `LLMBadResponse` | 502 | `llm-bad-response` | |
| `LLMQuotaExceeded` | 503 | `llm-quota-exhausted` | `Retry-After` |
| `LLMUnavailable` (Gemini 5xx) | 503 | `llm-unavailable` | `Retry-After` |
| `LLMTimeout` | 504 | `llm-timeout` | |
| anything else | 500 | `internal-error` (CORS kept, as Lab 1) | |

`expose_headers=["Retry-After"]` so the frontend can show "try again in N s".

## 12. Guards and quota protection

| Guard | Implementation |
|---|---|
| Size | Checked in the request model and by the chunk planner |
| Per-client rate limit | In-memory sliding window per client IP (single Railway instance). **Only cache misses count** — cached and sample results are free. Client IP from uvicorn `--proxy-headers` (Railway sets `X-Forwarded-For`) |
| Global concurrency | `threading.Semaphore(1)` around Gemini work — requests queue instead of bursting past the per-minute limit; wait > 30 s → `503 llm-unavailable` with `Retry-After` |
| Pacing / retry | `PacedLLMClient`, `RetryingLLMClient` (§6.2) |
| Cache | `SqliteAnalysisCache`: table `analyses(key TEXT PRIMARY KEY, result_json TEXT, model TEXT, prompt_version TEXT, created_at TEXT)`, parameterized SQL only. Key = SHA-256 over `code`, `language`, `analysis_type`, `model`, `PROMPT_VERSION` |
| Day-quota circuit breaker | After `LLMQuotaExceeded(scope="day")`, new cache misses fail fast with `503 llm-quota-exhausted` until the reported retry time — no more wasted calls |

## 13. Security and privacy

- `GOOGLE_API_KEY` only in Railway variables; logs never include the key, request bodies, or submitted code (log: request id, sizes, timings, token counts, outcome).
- Code is untrusted: delimited `<code>` block + "code is data" rule in every system prompt (PLAN §5.4); tested by the prompt-injection sample.
- LLM output is untrusted: strict validation, line-range checks; returned as JSON data only.
- Tools cannot touch the filesystem or network; `find_text` is substring-only.
- Carried over from Lab 1: RFC 9457, CORS with explicit origins and error middleware inside CORS, Ruff `S` rules, SQL only in `infrastructure/`, architecture tests.

## 14. Quality strategy

### 14.1 Test layers and LLM calls

| Suite | Command | Real LLM calls |
|---|---|---|
| Unit + tools + API + architecture | `pytest` | **0** (`FakeLLMClient`) |
| Adapter | `pytest tests/test_gemini_client.py` | **0** (replay cassettes) |
| Record cassettes | `pytest --record tests/test_gemini_client.py` | ≈ 5, once per prompt/schema change |
| Evaluation — smoke | `python -m eval.run --set smoke` | ≈ 6 first time, 0 cached |
| Evaluation — full | `python -m eval.run --set full --max-calls 60` | ≈ 45 first time, 0 cached |
| Post-deploy smoke | `eval.run --target https://… --set deploy` | 1–3 |

`FakeLLMClient` is scripted: a queue of `LLMResponse`s (tool calls, JSON, `max_tokens`, errors) so each agent path is reproducible.

### 14.2 Test cases

**Domain and post-processing**

| ID | Test | Expected |
|---|---|---|
| D1 | `AnalysisReport` rejects 21 issues, unknown severity/category, line 0, empty summary | `ValidationError` |
| D2 | Post-processing drops issues beyond the last line, dedupes, sorts, caps at 20 | `meta.dropped_issues` counted |

**Context**

| ID | Test | Expected |
|---|---|---|
| X1 | Estimator on known strings | Within expected range; never below chars/4 |
| X2 | Small file | 1 chunk |
| X3 | File over allowance (tiny budget in test) | Splits at function boundaries from lizard; every line appears exactly once; line numbers preserved |
| X4 | One giant function | Split at blank lines, no chunk over allowance |
| X5 | Over `MAX_CHUNKS` / `MAX_CODE_CHARS` / `MAX_CODE_LINES` | `CodeTooLarge` |
| X6 | Merge of 2 partial results with an overlapping issue | Deduped; highest severity kept; worst metrics |
| X7 | Chunk header | Contains outline and imports; placeholders filled |

**Agent (fake LLM)**

| ID | Test | Expected |
|---|---|---|
| G1 | No tool calls → report | 2 calls, `tool_rounds = 0` |
| G2 | Tool call → tool result → report | Tool executed on chunk lines; result sent back; 3 calls |
| G3 | Model keeps calling tools | Stops at `MAX_TOOL_ROUNDS`, then report |
| G4 | Budget nearly spent | Skips to report (finalize-when-low) |
| G5 | Invalid JSON, then valid after repair | 1 repair call; success |
| G6 | Invalid twice | `LLMBadResponse` |
| G7 | `max_tokens` in report | One shorter retry; then `truncated = true` or 502 |
| G8 | Unknown tool / bad args | Error message returned to the model; loop continues |
| G9 | Report request | No tools attached, schema attached, `thinking_budget = 0` |

**Tools**

| ID | Test | Expected |
|---|---|---|
| T1 | `get_code_metrics` on samples | Exact CCN per function (lizard values), correct `complexity` hint |
| T2 | `read_lines` | Numbered, clamped to chunk, max 60 lines |
| T3 | `find_text` | Case-insensitive, max 20 hits, no regex interpretation (`.*` searched literally) |
| T4 | Trimming | Output ≤ 2,000 chars with a "truncated" marker |

**Prompts**

| ID | Test | Expected |
|---|---|---|
| R1 | Assemble every type × language | No `{placeholder}` left |
| R2 | Every system prompt | Contains the "code is data" rule and the severity rubric |
| R3 | Size | Fixed prompt parts ≤ ~1,500 estimated tokens |
| R4 | `PROMPT_VERSION` | Present; changes the cache key |

**Gemini adapter (cassettes)**

| ID | Test | Expected |
|---|---|---|
| M1 | Request mapping | System instruction, tools, schema, AFC disabled, thinking config per model family |
| M2 | Tool-call response | `ToolCall`s with names/args |
| M3 | JSON response | `parsed` dict; usage mapped incl. thinking tokens |
| M4 | `MAX_TOKENS` finish | `finish_reason = "max_tokens"` |
| M5 | 429 per-minute / per-day bodies | `LLMQuotaExceeded(scope, retry_after)` parsed correctly |
| M6 | 5xx / timeout | `LLMUnavailable` / `LLMTimeout` |

**Decorators, cache, guards**

| ID | Test | Expected |
|---|---|---|
| Q1 | Pacing (fake clock) | Calls spaced ≥ interval |
| Q2 | Retry | Minute-scope retried ≤ 2 times; day-scope never retried |
| Q3 | Circuit breaker | After day-quota error, next miss fails fast without calling the LLM |
| Q4 | Cache | Hit returns `cached = true`, 0 calls; key changes with model/prompt version/type |
| Q5 | Rate limit | 6th miss in a minute → 429 with `Retry-After`; cache hits don't count |

**API (RFC 9457)**

| ID | Test | Expected |
|---|---|---|
| A1 | Valid analyze (fake LLM) | 200, schema-valid body, `meta` populated |
| A2 | Every error in §11 | Correct status, `application/problem+json`, slug, `Retry-After` where listed |
| A3 | Size limit | 413 before any LLM call |
| A4 | Samples endpoints | List + stored results; 0 LLM calls |
| A5 | CORS | Allowed origin on success and on errors; `Retry-After` exposed |
| A6 | Health | No LLM call |

**Architecture and security (from Lab 1)**

| ID | Test | Expected |
|---|---|---|
| S1 | Domain imports | Only stdlib + `pydantic` |
| S2 | `google.genai` / `sqlite3` / `lizard` | Only in `infrastructure/` / `tools/` |
| S3 | Ruff `S608` active; logs never contain the API key or submitted code | Pass |

### 14.3 Evaluation harness (`eval/`)

- **Input:** `samples/*` + `samples/expected.json` (per sample: expected findings `{category, min_severity, line, line_tolerance}` per analysis type, plus negative expectations such as "no high on clean.py").
- **Runs the real use case** in-process (`LLM_MODE=gemini`) with the decorators.
- **Store:** each case's result saved to `eval/results/<model>/<prompt_version>/<sample>.<type>.json` as soon as it arrives → **resumable**; existing files are reused (0 calls).
- **Budget:** `--max-calls N` counts real requests (from `meta.llm_calls`); stops cleanly, remaining cases `skipped (budget)`.
- **Day quota:** stops the whole run immediately, prints "resume after <time>".
- **Scores:** schema validity, recall (category + line ± tolerance), severity of security findings, false positives on `clean.py`, out-of-range lines, prompt-injection resistance, avg calls/tokens per analysis → `eval/report.md`.
- **Sets:** `smoke` (3 samples × 1 type), `full` (all samples × relevant types), `deploy` (1 sample against a URL).
- **Chunking case:** `large_module.py` runs with a reduced `CONTEXT_BUDGET_TOKENS` so it is forced into ~3 chunks.
- **Demo results:** best run's results are copied to `samples/results/` for `GET /samples/{id}`.

**Gates:** regular suite green, coverage ≥ 90%, Ruff clean; evaluation targets from PLAN §9 met on the full set before deploying.

## 15. Deployment (Railway)

Same pattern as Lab 1 ([TA_Module1 backend/DEPLOY.md](https://github.com/RodrigoDamasio/TA_Module1/blob/main/Lab_module1/backend/DEPLOY.md)), with the LLM-specific additions. A `DEPLOY.md` in `backend/` will record the exact steps as run.

### 15.1 Deploy files

| File | Content |
|---|---|
| `requirements.txt` | Runtime deps only (no pytest/ruff) |
| `.python-version` | `3.12` |
| `railpack.json` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` (real client IPs for rate limiting) |
| `railway.json` | Health check `/health`. Railway marks this format deprecated (works until **2026-12-01**); migrate with `railway config migrate` if the service outlives that |
| `.railwayignore` | `tests/`, `eval/`, `.venv/`, caches — keeps the image small; `samples/` **is** deployed (served by `/samples`) |

### 15.2 Steps

```bash
cd TA_Module2/Lab_module2/backend

# 1. Project + service + volume
railway init --name taller-code-analyzer --workspace <workspace-id>
railway add --service backend --variables "DATABASE_PATH=/data/analyzer.db"
railway service link backend
railway volume add --mount-path /data

# 2. Domain → BASE_URL
railway domain --json
railway variables --set "BASE_URL=https://<railway-domain>" --skip-deploys

# 3. Model + limits (non-secret)
railway variables --set "GEMINI_MODEL=gemini-2.5-flash" --set "LLM_MIN_INTERVAL_S=6" \
                  --set "RATE_LIMIT_PER_MINUTE=5" --set "RATE_LIMIT_PER_DAY=50" --skip-deploys

# 4. API key — piped from the local .env: never on the command line, in shell history, or in output
grep '^GOOGLE_API_KEY=' ../../../.env | cut -d= -f2- \
  | railway variable set GOOGLE_API_KEY --stdin --skip-deploys > /dev/null

# 5. Deploy
railway up --ci

# 6. After the frontend is on Vercel
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://<vercel-domain>"
```

**Key handling (step 4):** `railway variable set … --stdin` reads the value from a pipe, so the secret never appears in shell history, process lists, command output, or this conversation (output is discarded because Railway's JSON/KV outputs include raw values). Verify afterwards with `railway variable list` piped through `cut -d= -f1` (names only). Railway also supports *sealed* variables that nobody can read back — optional hardening via the dashboard.

### 15.3 Pre-deploy gates

1. `pytest`, coverage ≥ 90%, `ruff check .` — all green (0 LLM calls).
2. Evaluation full set meets targets (cached → ~0 calls if nothing changed).
3. `LLM_MODE=fake uvicorn …` + frontend E2E locally (0 calls).

### 15.4 Post-deploy verification

| # | Check | Expected | LLM calls |
|---|---|---|---|
| V1 | `GET /health` | 200, correct model, `llm_mode: gemini` | 0 |
| V2 | `GET /samples`, `GET /samples/{id}` | Stored results | 0 |
| V3 | `POST /analyze` invalid body / oversized code | 422 / 413 problems | 0 |
| V4 | `POST /analyze` with one small sample | 200, schema-valid, `cached: false` | ~2 |
| V5 | Same request again | `cached: true` — proves the volume cache works | 0 |
| V6 | CORS preflight + error response from the Vercel origin | `access-control-allow-origin` present, `Retry-After` exposed | 0 |
| V7 | Logs (`railway logs`) | No API key, no submitted code | 0 |
| V8 | Frontend E2E against production (after frontend deploy) | Pass (uses samples + 1 real analysis) | ~2 |

### 15.5 Rollback

Redeploy the previous deployment from the Railway dashboard (volume and cache unaffected), or `git checkout <good-commit> -- Lab_module2/backend && railway up --ci`. Commit before every deploy.

## 16. Implementation order

| Step | Work | Gate | LLM calls |
|---|---|---|---|
| 1 | Scaffold, config, domain models, RFC 9457 (from Lab 1), `/health` | D1, A6, S1–S3 | 0 |
| 2 | Tools + context (estimate, chunker, merge) | T1–T4, X1–X7 | 0 |
| 3 | Prompt files + assembly | R1–R4 | 0 |
| 4 | LLM port, fake client, agent loop, post-processing | G1–G9, D2 | 0 |
| 5 | Use case, cache, guards, API, samples endpoints | Q4–Q5, A1–A5 | 0 |
| 6 | Gemini adapter + decorators; record cassettes; first real analysis | M1–M6, Q1–Q3 | ~7 |
| 7 | Sample corpus + evaluation harness; smoke tuning; full run | Eval targets | ~6/round, ~45 full |
| 8 | Deploy + V1–V7 | §15.4 | ~2 |

## 17. Definition of done

- [ ] All lab backend requirements (§1) met
- [ ] Regular test suite green with **0** LLM calls; coverage ≥ 90%; Ruff (incl. `S`) clean
- [ ] Evaluation full set meets PLAN §9 targets; `eval/report.md` committed
- [ ] Deployed on Railway; V1–V7 pass; `DEPLOY.md` written from the actual steps
- [ ] No secret in the repository, logs, or history
