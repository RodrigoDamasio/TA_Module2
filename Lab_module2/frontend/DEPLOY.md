# Frontend Deployment — Vercel

Steps run to deploy the Code Analyzer UI (same pattern as Module 1).

**Result:** https://taller-code-analyzer.vercel.app

| Item | Value |
|---|---|
| Vercel scope / project | `rodrigodamasiojulio-9268` / `taller-code-analyzer` (Hobby) |
| Backend | https://backend-production-17bc.up.railway.app ([../backend/DEPLOY.md](../backend/DEPLOY.md)) |

## Steps

```bash
cd TA_Module2/Lab_module2/frontend

# 1. Create/link the project
vercel link --yes --project taller-code-analyzer

# 2. Backend URL — before building (NEXT_PUBLIC_* is inlined at build time)
printf 'https://backend-production-17bc.up.railway.app' | vercel env add NEXT_PUBLIC_API_URL production

# 3. Deploy
vercel --prod --yes

# 4. Allow the Vercel domain on the backend (CORS) — from ../backend
railway variables --set "FRONTEND_ORIGIN=http://localhost:3000,https://taller-code-analyzer.vercel.app"
```

`vercel link` printed *"Failed to link RodrigoDamasio/TA_Module2. You need to add a Login Connection to your GitHub account first"* — that is only the optional Git integration (auto-deploy on push). The project was created and CLI deploys work; connect GitHub in the Vercel dashboard if auto-deploys are wanted.

## Verification

| Check | Result |
|---|---|
| Page public | ✅ HTTP 200 |
| Bundle contains the Railway URL | ✅ |
| CORS preflight from the Vercel origin | ✅ active ~145 s after setting `FRONTEND_ORIGIN` (Railway redeploy) |
| E2E suite against production (E1–E6) | ✅ 6/6 — 0 Gemini calls (E1's snippet was already cached; samples are stored results) |

## Redeploy

```bash
npm run typecheck && npm run lint && npm test && npm run build
vercel --prod --yes
BASE_URL=https://taller-code-analyzer.vercel.app npm run test:e2e
```

Changing the backend URL requires a rebuild (`vercel env rm/add`, then `vercel --prod`). A new frontend domain must be added to `FRONTEND_ORIGIN` on Railway.
