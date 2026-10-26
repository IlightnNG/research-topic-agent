import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.LIT_E2E_BASE ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1, // 共享后端 DB，串行避免相互干扰
  retries: 1, // 真实 run 型 e2e 抗抖动；失败仍会报错
  reporter: [["list"]],
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.LIT_E2E_NO_SERVER
    ? undefined
    : [
        // 批次 4 / O：`npm run test:e2e` 单独运行也能起后端（已存在则复用）
        {
          command:
            "powershell -NoProfile -Command \". .\\scripts\\env.ps1; uv run uvicorn lit_agent.api.app:app --port 8000\"",
          cwd: "..",
          url: "http://127.0.0.1:8000/api/health",
          reuseExistingServer: true,
          timeout: 180_000,
        },
        {
          command: "npm run dev -- --port 5173",
          url: BASE,
          reuseExistingServer: true,
          timeout: 120_000,
        },
      ],
});
