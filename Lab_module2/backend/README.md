# Code Analyzer — Backend

FastAPI service with an LLM agent (Google Gemini) that reviews code and returns structured JSON: summary, issues, suggestions, metrics. Design: [../PLAN.md](../PLAN.md) · [../BACKEND_PLAN.md](../BACKEND_PLAN.md).

## Run locally

```bash
cd TA_Module2/Lab_module2/backend
source ../../../.venv/bin/activate          # Python 3.12 environment of the course
pip install -r requirements-dev.txt

# Real analyses (reads GOOGLE_API_KEY from the environment)
set -a && source ../../../.env && set +a
uvicorn app.main:app --reload               # http://localhost:8000/docs

# No key / no quota: canned answers for UI work
LLM_MODE=fake uvicorn app.main:app --reload
```

## API

| Method · Path | Purpose | LLM calls |
|---|---|---|
| `POST /analyze` | `{"code", "language", "analysis_type"?}` → report + `meta` | 0 if cached, typically 2–3 |
| `GET /samples` · `GET /samples/{id}?analysis_type=` | Demo samples with stored results | 0 |
| `GET /health` | Status, model, LLM mode | 0 |
| `GET /problems/{slug}` | RFC 9457 problem type docs | 0 |

- `language`: `python` · `javascript` · `typescript` · `java` · `go`
- `analysis_type`: `general` (default) · `security` · `performance`
- Errors are RFC 9457 `application/problem+json`: `400`, `413 code-too-large`, `422`, `429 rate-limited`, `502 llm-bad-response` / `llm-request-rejected`, `503 llm-quota-exhausted` / `llm-unavailable` (+ `Retry-After`), `504 llm-timeout`.

## How it works

```
app/
├── domain/          models (Pydantic contract), errors, ports (LLMClient, cache), CodeChunk
├── application/     AnalyzeCode use case, two-phase agent, context budget + chunking, prompts
├── tools/           get_code_metrics (lizard), read_lines, find_text — the agent's tools
├── prompts/         versioned prompt library (RCFG system prompt, personas, few-shot, phases)
├── infrastructure/  Gemini adapter, quota wrappers, SQLite cache, samples, demo LLM
└── api/             routes, RFC 9457 problems, rate limiter, wiring
```

1. **Cache** — identical code + language + type + model + prompt version → stored result, 0 calls.
2. **Context budget** — the code is numbered and measured; above the per-request budget it is split at function boundaries (lizard) into ≤ 4 chunks, each with a file outline.
3. **Investigate** — the model reasons step by step and may call the tools (max 3 rounds; 1 per chunk).
4. **Report** — a compacted conversation (code + investigation notes) asks for schema-constrained JSON; small defects are fixed locally, real schema errors get one repair call.
5. **Merge** — chunk results are merged (line numbers kept, duplicates removed, worst metrics).

Quota protection: pacing between calls, retry of short per-minute limits and provider overloads, a circuit breaker after the daily limit, one Gemini call at a time, per-client rate limit (cache hits are free), SDK auto-retries disabled.

## Quality checks

```bash
pytest -q                                   # 0 real LLM calls (fake LLM + recorded responses)
pytest -q --cov=app --cov-report=term-missing
ruff check . && ruff format --check .

# Evaluation against the real model — cached and resumable, capped by --max-calls
python -m eval.run --set smoke
python -m eval.run --set full --max-calls 60
python -m eval.record_cassettes             # re-record adapter fixtures (~3 calls)
```

`samples/` holds code with **deliberately planted issues** and `expected.json` (the answer key). It is excluded from Ruff on purpose.

## Configuration

See `app/config.py`. Main variables: `GOOGLE_API_KEY`, `GEMINI_MODEL` (default `gemini-3.5-flash-lite`; `gemini-3.8-flash` has only 20 free requests/day), `LLM_MODE` (`gemini`/`fake`), `LLM_MIN_INTERVAL_S`, `CONTEXT_BUDGET_TOKENS`, `MAX_CODE_CHARS`, `RATE_LIMIT_PER_MINUTE` / `_PER_DAY`, `DATABASE_PATH`, `BASE_URL`, `FRONTEND_ORIGIN`.
