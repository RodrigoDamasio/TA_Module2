# Frontend Plan — Code Analyzer UI

Frontend design for [PLAN.md](PLAN.md), consuming the deployed API ([BACKEND_PLAN.md](BACKEND_PLAN.md), live at https://backend-production-17bc.up.railway.app). Same stack and quality approach as Lab 1, adapted to a slow, quota-limited LLM backend.

## 1. Scope

| Lab requirement | How it is met |
|---|---|
| Paste or upload code | Monospace textarea with line/char counter + "Upload file" (reads the file in the browser; language auto-selected from the extension) |
| Language selector dropdown | `python` · `javascript` · `typescript` · `java` · `go` |
| "Analyze" button with loading state | Disabled while running; spinner + elapsed seconds ("usually 5–15 s"); `aria-busy` |
| Results panel: summary, issues color-coded by severity, suggestions, metrics | Summary card · issues sorted by severity, each with a colored severity **badge with text** (not color alone), category, line, the code line itself, and the suggested fix · suggestions list · metrics chips |
| Responsive design | Stacked on phones; input and results side by side on wide screens |

Additions driven by the backend's nature:

| Addition | Why |
|---|---|
| **Analysis type** selector (`general` / `security` / `performance`) | Lab asks for ≥ 2 analysis types |
| **"Try a sample"** menu | Loads a sample's code **and its stored result** — a full demo with **0 LLM calls** |
| **Meta line** (model, calls, tokens, cached) | Makes the agent's work and cost visible |
| **Friendly RFC 9457 errors** | `detail` from the problem body; field errors for 422; the size limit for 413; a **Retry-After countdown** for 429/503 (button disabled until it ends) |
| **Privacy notice** | Code is sent to Google Gemini (free tier) — don't paste secrets |
| **Client-side size check** | Counter turns red and Analyze is disabled above 60,000 chars — no wasted request |

## 2. Stack

| Tool | Choice |
|---|---|
| Node | 24 (`nvm use 24`) |
| Framework | Next.js 16 (App Router), TypeScript strict, Tailwind v4 |
| Validation | **Zod** — every API response is parsed with a schema mirroring the backend's Pydantic models; a response that does not match is an error, never rendered half-valid |
| Tests | Vitest + Testing Library (unit, component) · Playwright with the installed Google Chrome (`channel: "chrome"`, as in Lab 1) |

## 3. Structure

```
frontend/
├── app/            layout.tsx · page.tsx · globals.css
├── components/
│   ├── Analyzer.tsx      # state + orchestration (client component)
│   ├── CodeInput.tsx     # textarea, counter, upload, language/type selectors, samples menu
│   └── Results.tsx       # summary, issues, suggestions, metrics, meta
├── lib/
│   ├── schemas.ts        # Zod schemas (AnalysisResult, Sample, Problem)
│   ├── api.ts            # analyze(), listSamples(), getSample() + error mapping
│   ├── languages.ts      # languages, analysis types, detect language from file name
│   └── severity.ts       # order + colors per severity
├── tests/          unit + component (Vitest)
└── e2e/            Playwright
```

## 4. API client and errors

- `NEXT_PUBLIC_API_URL` (build-time, as in Lab 1); default `http://localhost:8000`.
- Timeout **120 s** (a chunked analysis can take ~40 s with pacing).
- Errors become `ApiError { kind, message, retryAfter?, fieldErrors? }`:

| Response | `kind` | Shown to the user |
|---|---|---|
| 422 `validation-error` | `validation` | Each field error (`#/code` → "Code: must not be blank") |
| 413 `code-too-large` | `too_large` | Problem `detail` (states the limit) |
| 429 `rate-limited` | `rate_limited` | "Too many analyses — try again in N s" + countdown |
| 503 `llm-quota-exhausted` / `llm-unavailable` | `unavailable` | Problem `detail` + countdown from `Retry-After` |
| 502 / 504 | `llm_failed` | Problem `detail` + "try again" |
| Other non-2xx | `server` | Generic message |
| `fetch` throws / aborted by timeout | `network` / `timeout` | "Can't reach the analyzer" / "took too long" |
| 200 with a body that fails the Zod schema | `invalid_response` | "Unexpected response from the server" |

## 5. Quality strategy

| Level | What | Real LLM calls |
|---|---|---|
| Unit | `api.ts` (every row of §4, request shape, Zod rejection), `languages.ts`, `severity.ts` | 0 (fetch mocked) |
| Component | `Analyzer` behaviors (C1–C10 below) | 0 (api mocked) |
| E2E local | Real backend started with **`LLM_MODE=fake`** + real frontend: full integration, no quota | **0** |
| E2E production | Same suite against Vercel + Railway; samples are free, **one** real analysis | ~2 |
| Also | `tsc`, ESLint, `next build`, coverage ≥ 80% | 0 |

**Component tests**

| ID | Test |
|---|---|
| C1 | Initial render: labelled textarea, selectors, privacy notice; Analyze disabled while empty |
| C2 | Typing enables Analyze; the counter shows lines and chars; > 60,000 chars disables it |
| C3 | Upload `x.ts` → code filled, language set to TypeScript |
| C4 | Analyze sends `{code, language, analysis_type}`; loading state with elapsed time; double submit blocked |
| C5 | Results: summary, issues sorted critical → info with severity text + color class, line preview, suggestion, metrics, meta |
| C6 | No issues → "No issues found" message |
| C7 | Error with field errors (422) shows each field |
| C8 | 429/503 → message with countdown; Analyze disabled until it reaches 0 (fake timers) |
| C9 | Sample menu → code, language, type and the stored result appear without calling analyze |
| C10 | New analysis clears the previous error/result |

**E2E** (Playwright)

| ID | Test |
|---|---|
| E1 | Paste code → Analyze → results render (fake-LLM backend locally) |
| E2 | Load a sample → stored result renders (0 calls) |
| E3 | Invalid/oversized input → friendly error; backend down (`page.route` abort) → network message |
| E4 | 503 with `Retry-After` (route mocked) → countdown shown |
| E5 | Mobile 375×667: no horizontal scroll, all controls reachable |
| E6 | Accessibility: axe finds no serious/critical violations |
| E7 | Production: E2 + E5 + E6 + one real analysis against the live URL |

## 6. Deployment (Vercel)

Same steps as Lab 1 ([Module 1 frontend/DEPLOY.md](https://github.com/RodrigoDamasio/TA_Module1/blob/main/Lab_module1/frontend/DEPLOY.md)):

```bash
cd TA_Module2/Lab_module2/frontend
vercel link --yes --project taller-code-analyzer
printf 'https://backend-production-17bc.up.railway.app' | vercel env add NEXT_PUBLIC_API_URL production
vercel --prod --yes
# then, from ../backend:
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://<vercel-domain>"
```

Post-deploy: page public (200), bundle contains the Railway URL, CORS preflight from the Vercel origin, E7.

## 7. Definition of done

- [ ] All lab frontend requirements (§1)
- [ ] typecheck, lint, unit/component tests (≥ 80% coverage), build — 0 LLM calls
- [ ] E1–E6 pass locally against the fake-LLM backend
- [ ] Deployed to Vercel; CORS updated on Railway; E7 passes on production
- [ ] `DEPLOY.md` with the steps run
