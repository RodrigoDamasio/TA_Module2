# Backend Deployment — Railway

The exact steps used to deploy the Code Analyzer API, in the order they were run.

**Result:** https://backend-production-17bc.up.railway.app ([API docs](https://backend-production-17bc.up.railway.app/docs))

| Item | Value |
|---|---|
| Railway project | `taller-code-analyzer` |
| Service / environment | `backend` / `production` |
| Volume | `backend-volume` mounted at `/data` (SQLite result cache) |
| Builder | Railpack, Python 3.12, pip |
| Model | `gemini-3.5-flash-lite` (Google AI Studio free tier) |

## Prerequisites

- Railway CLI logged in (`railway login`, done in Module 1).
- `GOOGLE_API_KEY` in the course's `.env` (`Taller_Academy/.env`, git-ignored).
- All gates green: `pytest -q` (0 LLM calls), `ruff check .`, full evaluation meets targets ([eval/report_full.md](eval/report_full.md)).
- Work committed (rollback point).

## Files that configure the deploy

| File | Purpose |
|---|---|
| `requirements.txt` + `.python-version` | Python 3.12 pip project (runtime deps only) |
| `railpack.json` | Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` — proxy headers give the real client IP to the rate limiter |
| `railway.json` | Health check `GET /health` (format deprecated by Railway after 2026-12-01 — migrate with `railway config migrate`) |
| `.railwayignore` | Keeps `tests/`, `eval/`, caches out of the image; `samples/` **is** deployed (served by `/samples`) |

## Steps

```bash
cd TA_Module2/Lab_module2/backend

# 1. Project, service (with the cache path), volume, public domain
railway init --name taller-code-analyzer --workspace <workspace-id>
railway add --service backend --variables "DATABASE_PATH=/data/analyzer.db"
railway service link backend
railway volume add --mount-path /data
railway domain --json            # → https://backend-production-17bc.up.railway.app

# 2. Non-secret settings
railway variables --set "BASE_URL=https://backend-production-17bc.up.railway.app" \
  --set "GEMINI_MODEL=gemini-3.5-flash-lite" --set "LLM_MIN_INTERVAL_S=6" \
  --set "RATE_LIMIT_PER_MINUTE=5" --set "RATE_LIMIT_PER_DAY=50" --skip-deploys

# 3. API key — piped from .env: never on the command line, in history, or in output
grep '^GOOGLE_API_KEY=' ../../../.env | cut -d= -f2- | tr -d '\n' \
  | railway variable set GOOGLE_API_KEY --stdin --skip-deploys > /dev/null

# 4. Verify without revealing values: names only, then compare fingerprints
railway variables --kv | cut -d= -f1
a=$(railway variables --kv | grep '^GOOGLE_API_KEY=' | cut -d= -f2- | tr -d '\n' | sha256sum)
b=$(grep '^GOOGLE_API_KEY=' ../../../.env | cut -d= -f2- | tr -d '\n' | sha256sum)
[ "$a" = "$b" ] && echo "key matches"

# 5. Deploy
railway up --ci
```

**After the frontend is on Vercel** (CORS; redeploys automatically):

```bash
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://<vercel-domain>"
```

## Final environment variables

| Variable | Value |
|---|---|
| `GOOGLE_API_KEY` | *(secret, set via stdin)* |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `DATABASE_PATH` | `/data/analyzer.db` |
| `BASE_URL` | `https://backend-production-17bc.up.railway.app` |
| `LLM_MIN_INTERVAL_S` | `6` |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_PER_DAY` | `5` / `50` per client IP |
| `FRONTEND_ORIGIN` | default `http://localhost:3000` until the frontend is deployed |

## Post-deploy verification (results)

| # | Check | Result | LLM calls |
|---|---|---|---|
| V1 | `GET /health` | ✅ `{"status":"ok","model":"gemini-3.5-flash-lite","llm_mode":"gemini"}` | 0 |
| V2 | `GET /samples`, `GET /samples/xss?analysis_type=security` | ✅ 9 samples; stored result (lines 8 critical, 4 high) | 0 |
| V3 | Invalid language / 70,000-char code | ✅ `422 validation-error` / `413 code-too-large`, `application/problem+json` | 0 |
| V4 | Real analysis (`divide(10, 0)`) | ✅ `high/bug` at line 4; 2 calls, 2,382 input tokens, ~8.5 s | 2 |
| V5 | Same request again | ✅ `cached: true` from the volume | 0 |
| V6 | CORS preflight + error response | ✅ `access-control-allow-origin` on both; `Retry-After` exposed | 0 |
| V7 | `railway logs` | ✅ 0 occurrences of the API key or submitted code; sizes/counters only | 0 |
| V8 | Frontend E2E against production | pending — after the frontend deploy | ~2 |

## Problems hit

None during this deploy — the Lab 1 lessons were applied up front (`railpack.json` start command, volume before first run). Found earlier, during implementation: `gemini-2.5-*` models closed to new users; `gemini-3.8-flash` free tier is 20 requests/day (→ `gemini-3.5-flash-lite`); misleading `retryDelay` on daily-quota errors (→ wait until midnight Pacific).

## Quota notes

The deployed app shares the key's free-tier quota with every caller of the public URL. Protections: per-IP rate limit (cache hits and samples are free), result cache, size limits, one Gemini call at a time, circuit breaker after the daily limit. With billing **not** enabled on the Google project, the worst case is "limit reached" until midnight Pacific — never a charge.

## Redeploy / rollback

```bash
pytest -q && ruff check . && git commit ...   # gates + rollback point
railway up --ci
```

Rollback: Railway dashboard → `backend` → Deployments → previous → Redeploy (volume/cache unaffected).
