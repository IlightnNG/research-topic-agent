import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.LIT_E2E_BASE ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  // Serial + no retries keeps failures honest and avoids doubled wall time.
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["line"]],
  use: {
    baseURL: BASE,
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.LIT_E2E_NO_SERVER
    ? undefined
    : [
        {
          command:
            "powershell -NoProfile -Command \". .\\scripts\\env.ps1; $env:LIT_AGENT_PIPELINE__LLM='off'; $env:LIT_AGENT_STORAGE__DATA_ROOT='D:\\lit-agent-store\\e2e-data'; uv run python scripts/seed_e2e_store.py; uv run uvicorn lit_agent.api.app:app --port 8000\"",
          cwd: "..",
          url: "http://127.0.0.1:8000/api/health",
          reuseExistingServer: true,
          timeout: 90_000,
        },
        {
          command: "npm run dev -- --port 5173",
          url: BASE,
          reuseExistingServer: true,
          timeout: 60_000,
        },
      ],
});
