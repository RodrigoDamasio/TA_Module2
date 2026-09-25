# Lab 2 — Big Picture Plan: Code Analyzer Agent

Solution-level plan for [Lab2_Code_Analyzer.md](Lab2_Code_Analyzer.md). Detailed designs come later in `BACKEND_PLAN.md` and `FRONTEND_PLAN.md`.

## 1. What we are building

A web app where a user pastes or uploads code, picks the language and the kind of analysis, and gets back a **structured review**: summary, issues (with severity, line, category, fix), general suggestions, and metrics.

Behind it, an **agent** calls an LLM (Google Gemini), lets the model use **tools** that inspect the code deterministically, and forces the final answer into a **validated JSON schema**.

## 2. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Backend | Python 3.12 · FastAPI · Pydantic | Proven in Lab 1 (layers, RFC 9457, tests, Railway deploy) |
| Frontend | Next.js 16 · TypeScript · Tailwind | Proven in Lab 1; native on Vercel |
| LLM provider | **Google Gemini** via the official `google-genai` SDK | The only working key (`GOOGLE_API_KEY`, free tier). Other providers plug in behind the same abstraction later |
| Model | Configurable (`GEMINI_MODEL`); **pinned** version, not a `-latest` alias | Reproducible evaluations and cache keys. Candidates available to the key: `gemini-2.5-flash` (default), `gemini-2.5-flash-lite` (cheaper, for prompt iteration); newer 3.x models can be compared in the evaluation |
| Analysis types | `general`, `security`, `performance` | Lab requires ≥ 2 (general + security **or** performance) — we do all three, one system prompt each |
| Agent pattern | **Two phases:** *investigate* (tool calls) → *report* (structured JSON, no tools) | Keeps tool use and schema-constrained output in separate requests, so it works regardless of whether a model supports both in one call; also the natural place to stop the loop when the context budget runs low |
| Context budget | Self-imposed per-request token budget (≈ 16K, configurable) | Free-tier tokens-per-minute limits, latency, and answer quality — see §6 |
| Testing | Zero LLM calls by default; real calls only in an opt-in, cached, resumable evaluation | Free-tier quota must never block us — see §8 |
| Storage | SQLite on a Railway volume, only for the **result cache** | Same pattern as Lab 1; no user accounts or history |

## 3. Architecture

```mermaid
flowchart LR
    user(["👤 User<br/>(browser)"])

    subgraph vercel["☁️ Vercel"]
        fe["Next.js frontend<br/>paste / upload code<br/>language + analysis type<br/>results panel"]
    end

    subgraph railway["☁️ Railway"]
        api["FastAPI API<br/>POST /analyze · GET /samples<br/>GET /health · GET /problems/{slug}"]
        guard["Guards<br/>size limit · rate limit"]
        agent["Analyzer agent<br/>context budget · chunking<br/>investigate → report"]
        tools["Tools (local, deterministic)<br/>metrics · read lines · search"]
        cache[("SQLite cache<br/>💾 volume /data")]
    end

    gemini["🤖 Google Gemini API<br/>(free tier)"]

    user -- "code + options" --> fe
    fe -- "POST /analyze (HTTPS, CORS)" --> api
    api --> guard --> agent
    agent -- "lookup / store by hash" --> cache
    agent -- "prompt + code (+ tool results)" --> gemini
    gemini -- "tool calls / structured JSON" --> agent
    agent -- "runs" --> tools
    api -- "AnalysisResult JSON<br/>or RFC 9457 problem" --> fe
    fe -- "summary · color-coded issues<br/>suggestions · metrics" --> user
```

### Agent flow for one analysis

```mermaid
sequenceDiagram
    participant API as POST /analyze
    participant C as Cache
    participant A as Agent
    participant T as Tools
    participant G as Gemini

    API->>C: hash(code, language, type, model, prompt version)
    alt cached
        C-->>API: stored result (meta.cached = true, 0 LLM calls)
    else not cached
        API->>A: analyze(code, language, type)
        A->>A: estimate tokens, split into chunks if over budget
        loop each chunk (max 4)
            A->>G: investigate: system prompt + numbered code + tool definitions
            opt tool call (max 3 rounds; 1 per chunk when chunked)
                G-->>A: call get_metrics / read_lines / find_text
                A->>T: run tool locally
                T-->>A: result (trimmed to size)
                A->>G: tool result
            end
            A->>G: report: "answer now" + JSON schema, no tools
            G-->>A: structured JSON
            A->>A: validate with Pydantic (one repair retry if invalid)
        end
        A->>A: merge chunks: shift line numbers, dedupe, combine metrics
        A->>C: store result
        A-->>API: AnalysisResult + meta
    end
```

## 4. Components

| Component | Responsibility |
|---|---|
| **Domain** | `AnalysisRequest`, `AnalysisResult`, `Issue`, `Metrics` models and rules (severity/category enums, line numbers within the file, list caps) |
| **Application** | `AnalyzeCode` use case: cache → budget/chunking → agent → merge → cache |
| **LLM abstraction** | `LLMClient` port (send messages + tools, or request schema-constrained JSON; return text/tool calls + token usage). Adapters: `GeminiClient` (real), `FakeLLMClient` (tests), `ReplayLLMClient` (recorded responses) |
| **Prompts** | One versioned system prompt per analysis type + shared output rules; `PROMPT_VERSION` feeds the cache key |
| **Tools** | `get_code_metrics` (lines, functions, cyclomatic complexity), `read_lines(start, end)`, `find_text(text)` (plain substring search — no user/LLM regex, avoiding ReDoS) |
| **Context manager** | Token estimation, budget allocation, structure-aware chunking, tool-result trimming, finalize-when-low |
| **Guards** | Max code size (→ 413), per-client rate limit (→ 429), global concurrency limit toward Gemini |
| **Cache** | SQLite on the volume; key = SHA-256 of code + language + type + model + prompt version |
| **Samples** | Code files with planted, documented issues + `expected.json`; used by tests, evaluation, and frontend demo |
| **Evaluation harness** | Runs the real agent over samples, scores against `expected.json`; cached, resumable, call-budgeted |
| **Frontend** | Input (paste/upload), selectors, loading state, results panel, sample buttons, friendly errors |

## 5. API contract (summary)

**`POST /analyze`**

```json
{ "code": "def f(x):\n  ...", "language": "python", "analysis_type": "security" }
```

**`200 OK`**

```json
{
  "summary": "2–3 sentence overview.",
  "issues": [
    {
      "severity": "high",
      "line": 12,
      "category": "security",
      "description": "SQL query built with an f-string from user input.",
      "suggestion": "Use a parameterized query: cursor.execute(sql, (user_id,))."
    }
  ],
  "suggestions": ["Add type hints to public functions."],
  "metrics": { "complexity": "medium", "readability": "good", "test_coverage_estimate": "none" },
  "meta": {
    "analysis_type": "security", "model": "gemini-2.5-flash", "prompt_version": "1",
    "cached": false, "chunks": 1, "tool_rounds": 1, "llm_calls": 2,
    "tokens": { "input": 1830, "output": 412 }, "truncated": false
  }
}
```

- `severity`: `critical` · `high` · `medium` · `low` · `info`
- `category`: `bug` · `security` · `performance` · `style` · `maintainability`
- `language`: `python` · `javascript` · `typescript` · `java` · `go` (extendable)

**Other endpoints:** `GET /health` · `GET /samples` (list) · `GET /samples/{id}` (code + stored result — no LLM call) · `GET /problems/{slug}`.

**Errors (RFC 9457 `application/problem+json`, as in Lab 1):**

| Status | Problem | When |
|---|---|---|
| 400 | `malformed-request` | Body is not JSON |
| 413 | `code-too-large` | Code above the hard size limit (limit stated in `detail`) |
| 422 | `validation-error` | Bad field values, empty code, unsupported language/type |
| 429 | `rate-limited` + `Retry-After` | This client sent too many analyses |
| 502 | `llm-bad-response` | Model output still invalid after one repair retry |
| 503 | `llm-quota-exhausted` + `Retry-After` | Gemini quota reached (per-minute or per-day) |
| 504 | `llm-timeout` | Gemini did not answer in time |
| 500 | `internal-error` | Anything unexpected (logged, CORS headers kept) |

## 6. Context window management

| Mechanism | Behavior |
|---|---|
| **Per-request budget** (≈ 16K tokens) | Split into: system prompt + tool definitions (fixed) · numbered code · tool traffic · reserved output |
| **Local token estimate** | Before each call, conservative chars-per-token estimate (≈ 3 chars/token for code, measured in Module 1). Actual usage from Gemini's response is recorded in `meta.tokens` and compared in tests/evaluation |
| **Numbered lines** | Code is sent as `12│ ...` so the model reports accurate line numbers (counted in the budget) |
| **Chunking (map → reduce)** | Code over budget is split at function/class boundaries (Python AST; blank-line/brace heuristics otherwise), each chunk with a header of imports + file outline; results merged with line-number offsets and de-duplication. Max 4 chunks |
| **Hard limit** | Beyond max chunks → `413 code-too-large` instead of a partial analysis |
| **Agent-loop growth** | Tool results trimmed; max 3 tool rounds (1 per chunk when chunked); when the remaining budget is low, skip straight to the *report* phase |
| **Output fits** | Schema caps (≤ 20 issues, length limits); on `MAX_TOKENS`, one retry asking for a shorter answer, otherwise return with `meta.truncated = true` |
| **Stateless** | No conversation memory between requests — nothing accumulates |

## 7. Quota protection (free tier)

| Where | Protection |
|---|---|
| **Everywhere** | Model and limits come from configuration; no hard-coded quota numbers (Google changes them; AI Studio and the 429 error body are the source of truth) |
| **Gemini client** | Client-side pacing below the per-minute limit; on 429, read which quota and the retry delay: per-minute → wait and retry (bounded); per-day → stop immediately |
| **Production** | Result cache; per-client rate limit; max code size; global concurrency limit; quota errors become `503` + `Retry-After` and a friendly frontend message; sample buttons show stored results (0 calls) |
| **Development** | Fake/replayed LLM for all regular tests; evaluation cached, resumable, with `--max-calls`; lighter model for prompt iteration |

## 8. Test strategy (overview)

| Layer | Real LLM calls | Checks |
|---|---|---|
| Unit (fake LLM) | 0 | Prompt building, schema validation, bad-LLM-output handling, context budget, chunking + line offsets, merge, guards, errors |
| Tools | 0 | Deterministic outputs on the samples (exact complexity values, line reads, search) |
| Adapter (recorded Gemini responses) | 0 (≈ 5 once to record) | Gemini request/response mapping incl. tool calls, 429 parsing |
| API | 0 | Endpoints, validation, RFC 9457, CORS, rate limit, 413 |
| **Evaluation** (opt-in `pytest -m live` / script) | smoke ≈ 6, full ≈ 45 first run; **0 when cached** | Schema validity 100%, recall ≥ 90% of planted issues (category + line ±1), severity of security issues, no `high` issues on clean code, no out-of-range lines, prompt-injection resistance |
| Frontend unit/component/E2E | 0 (mocked backend) | Input, selectors, loading, color-coded results, errors, responsive, accessibility |
| Post-deploy smoke | 1–3 | One real analysis end to end on production |

### Sample corpus (`backend/samples/`)

| Sample | Planted issue(s) | Expectation |
|---|---|---|
| `python/sql_injection.py` | Query built with f-string | `security`, ≥ `high`, correct line |
| `python/hardcoded_secret.py` | API key in source | `security`, ≥ `high` |
| `python/slow_lookup.py` | Nested loop instead of a set | `performance` |
| `python/buggy.py` | Mutable default argument, bare `except:` | `bug` |
| `javascript/xss.js` | `innerHTML` with user input, `eval` | `security` |
| `typescript/loose_types.ts` | `any` everywhere, no error handling | `style` / `maintainability` |
| `python/clean.py` | None (negative control) | No `high`/`critical` issues |
| `python/prompt_injection.py` | Comment telling the model to report nothing, next to a real vulnerability | Vulnerability still reported |
| `python/large_module.py` | Several hundred lines, issue in a later chunk | Found at the correct original line after chunking |

## 9. Security and privacy

- **API key** only on the backend (Railway variable); never in the frontend bundle, logs, or error responses.
- **Code is untrusted input**: it goes to the model as clearly delimited data; system prompts state that instructions inside the code must be ignored (tested with the prompt-injection sample).
- **LLM output is untrusted too**: validated against the schema; line numbers checked against the file; rendered in the frontend as text (no HTML injection).
- **Privacy**: submitted code is sent to Google. Under Google's current terms, free-tier API content may be used to improve their products — the UI will warn users not to paste secrets or proprietary code (verify the terms at deploy time).
- **Abuse**: size limit, rate limit, and cache limit the cost any one visitor can cause.
- **Carry-over from Lab 1**: RFC 9457 errors, CORS with explicit origins, Ruff security rules, no SQL built from strings.

## 10. Target structure

```
Lab_module2/
├── Lab2_Code_Analyzer.md
├── PLAN.md                  ← this file
├── BACKEND_PLAN.md          ← next
├── FRONTEND_PLAN.md         ← next
├── backend/                 → Railway
│   ├── app/                 # domain / application / infrastructure / api (Lab 1 layering)
│   │   ├── prompts/         # versioned system prompts per analysis type
│   │   └── tools/           # agent tools
│   ├── samples/             # code corpus + expected.json
│   ├── eval/                # evaluation harness + cached results
│   ├── tests/               # unit, adapter (recorded), API
│   └── DEPLOY.md
└── frontend/                → Vercel
    ├── app/ components/ lib/
    ├── tests/ e2e/
    └── DEPLOY.md
```

## 11. Phases

| # | Phase | LLM calls | Output |
|---|---|---|---|
| 0 | **Prerequisites** — confirm which pinned models the free tier serves (1 tiny call each for 2 models), check limits in AI Studio | ~2 | Model choice recorded |
| 1 | **Backend core** — domain models, `/analyze` with the fake LLM, RFC 9457, guards | 0 | API works end to end with fake answers |
| 2 | **LLM integration** — `GeminiClient`, prompts, two-phase agent, tools; record adapter responses | ~5 | Real analyses locally |
| 3 | **Context management** — budget, chunking, merge, truncation handling | 0 | Large inputs handled or rejected cleanly |
| 4 | **Samples + evaluation** — corpus, harness, prompt tuning on the smoke set, one full run | ~6 per tuning round, ~45 full | Scored evaluation report |
| 5 | **Production hardening** — cache, rate limit, quota errors, sample endpoint | 0 | Quota-safe API |
| 6 | **Frontend** — input, selectors, results panel, samples, errors, responsive | 0 | Local app against local backend |
| 7 | **Deploy** — Railway (new project + volume + key) and Vercel; post-deploy smoke + E2E | 1–3 | Live URLs |
| 8 | **Extensions** (if time) — caching (already done in 5), language detection, diff analysis, multi-file | varies | — |

### Deliverables → phases

| Deliverable | Phase |
|---|---|
| Working code analyzer API | 1–3 |
| Custom system prompt for analysis | 2, tuned in 4 |
| Structured JSON output | 1 (schema), 2 (from the model) |
| ≥ 2 analysis types | 2 (general, security, performance) |
| Deployed to Railway/Vercel | 7 |
| Tested with sample code | 4 |
| Web frontend with input + results | 6 |
| Application URL | 7 |

## 12. External tasks (you)

| # | Task | Needed for |
|---|---|---|
| 1 | Check the free-tier limits for the chosen model in Google AI Studio (they change) | Phase 0 |
| 2 | Approve putting `GOOGLE_API_KEY` into the Railway service variables (done via CLI from `.env`, never printed) | Phase 7 |
| 3 | *(Optional)* A separate key for production, so testing can't exhaust the live app's quota — check Google's terms | Phase 7 |

Railway and Vercel CLIs are already installed and logged in (Module 1).

## 13. Risks

| Risk | Mitigation |
|---|---|
| Free-tier limits or model availability change | Configurable model; Phase 0 check; quota handling that stops cleanly |
| Model returns invalid JSON / invents lines | Schema-constrained output, Pydantic validation, one repair retry, line-range checks |
| Non-deterministic answers make tests flaky | Deterministic suites use fakes/recordings; evaluation uses thresholds, not exact matches |
| Prompt injection through submitted code | Delimited input, explicit instruction, dedicated sample in the evaluation |
| Chunking splits context and hides cross-function bugs | File outline in every chunk header; chunking only above budget; max 4 chunks |
| Lab time budget (1h15) | Core path (phases 1, 2, 6, 7) first; context depth, evaluation breadth, and extensions scale with time available |
