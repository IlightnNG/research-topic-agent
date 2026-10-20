import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.LIT_E2E_BASE ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.LIT_E2E_NO_SERVER
    ? undefined
    : {
        command: "npm run dev -- --port 5173",
        url: BASE,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
