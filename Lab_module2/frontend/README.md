# Code Analyzer — Frontend

**Live:** https://taller-code-analyzer.vercel.app · API: https://backend-production-17bc.up.railway.app · deployment: [DEPLOY.md](DEPLOY.md) · design: [../FRONTEND_PLAN.md](../FRONTEND_PLAN.md)

Next.js 16 + TypeScript + Tailwind. Paste or upload code, pick the language and the analysis type (general / security / performance), and get a summary, issues color-coded by severity (with the code line and the fix), suggestions, and metrics. "Try a sample" shows stored results without using any LLM quota.

## Run locally (Node 24)

```bash
cd TA_Module2/Lab_module2/frontend
nvm use 24 && npm install
npm run dev                  # http://localhost:3000 — API from .env.local (http://localhost:8000)

# Backend without quota, in another terminal:
cd ../backend && LLM_MODE=fake ../../../.venv/bin/uvicorn app.main:app --port 8000
```

## Quality checks

```bash
npm run typecheck && npm run lint
npm test                     # unit + component (Vitest), API mocked
npm run test:coverage        # thresholds 80%
npm run build
npm run test:e2e             # Playwright: starts the real backend with LLM_MODE=fake + this app (0 quota)
BASE_URL=https://taller-code-analyzer.vercel.app npm run test:e2e   # against production
```

API responses are validated with **Zod** (`lib/schemas.ts`, mirroring the backend's Pydantic models); errors follow RFC 9457 and are mapped in `lib/api.ts`. E2E runs on the installed Google Chrome (`channel: "chrome"`), because Playwright's Chromium does not support Ubuntu 20.04.
