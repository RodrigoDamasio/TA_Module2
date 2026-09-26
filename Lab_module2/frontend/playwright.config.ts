import { defineConfig, devices } from "@playwright/test";

// BASE_URL=https://<vercel-domain> runs the suite against production (E7) instead of local servers.
const deployedUrl = process.env.BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000, // a real analysis in production can take ~10-40 s
  reporter: [["list"]],
  use: {
    baseURL: deployedUrl ?? "http://localhost:3000",
    // Playwright's bundled Chromium is not supported on Ubuntu 20.04: use the installed Chrome.
    channel: "chrome",
    trace: "retain-on-failure",
  },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
  webServer: deployedUrl
    ? undefined
    : [
        {
          // Real backend with a fake LLM: full integration, zero quota.
          command: "../../../.venv/bin/uvicorn app.main:app --port 8000",
          cwd: "../backend",
          url: "http://localhost:8000/health",
          env: { LLM_MODE: "fake", DATABASE_PATH: "e2e.db", FRONTEND_ORIGIN: "http://localhost:3000" },
          reuseExistingServer: true,
        },
        {
          command: "npm run dev",
          url: "http://localhost:3000",
          env: { NEXT_PUBLIC_API_URL: "http://localhost:8000" },
          reuseExistingServer: true,
        },
      ],
});
