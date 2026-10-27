import { expect, test } from "@playwright/test";
import type { Page, APIRequestContext } from "@playwright/test";

const TOPIC = "e2e-topic";

type RunItem = { id: string; state: string };
type ReportPayload = { sections?: Array<{ body: string }> };

/** Wait until the newest run is no longer running (avoids topic lock). */
async function waitTopicIdle(page: Page): Promise<void> {
  const first = page.locator(".run-list li").first();
  if (await first.count()) {
    await expect(first).not.toContainText("running", { timeout: 30_000 });
  }
}

/** Find an existing report whose sections contain `[C#]` citations. */
async function findReportRun(request: APIRequestContext): Promise<string | null> {
  const runs = await request.get(`/api/topics/${TOPIC}/runs?limit=10`);
  if (!runs.ok()) return null;
  const payload = (await runs.json()) as { items: RunItem[] };
  for (const run of payload.items) {
    const report = await request.get(`/api/runs/${run.id}/report`);
    if (!report.ok()) continue;
    const data = (await report.json()) as ReportPayload;
    if ((data.sections ?? []).some((section) => /\[C\d+\]/.test(section.body))) {
      return run.id;
    }
  }
  return null;
}

/** Generate a report through the API and wait for it to finish. */
async function generateRun(request: APIRequestContext): Promise<string> {
  await expect
    .poll(
      async () => {
        const runs = await request.get(`/api/topics/${TOPIC}/runs?limit=1`);
        if (!runs.ok()) return "unknown";
        const body = (await runs.json()) as { items: RunItem[] };
        return body.items[0]?.state ?? "idle";
      },
      { timeout: 30_000, intervals: [500] },
    )
    .not.toBe("running");

  const created = await request.post(`/api/topics/${TOPIC}/run`, {
    data: { focus_hint: null, wait: false },
  });
  expect(created.ok()).toBeTruthy();
  const { run_id: runId } = (await created.json()) as { run_id: string };
  await expect
    .poll(
      async () => {
        const run = await request.get(`/api/runs/${runId}`);
        return run.ok() ? ((await run.json()) as RunItem).state : "missing";
      },
      { timeout: 30_000, intervals: [500] },
    )
    .toBe("succeeded");
  return runId;
}

test.beforeAll(async ({ request }) => {
  // Idempotent seed: create the topic only if missing.
  const listed = await request.get("/api/topics");
  const items = (await listed.json()) as Array<{ id: string }>;
  if (!items.some((item) => item.id === TOPIC)) {
    await request.post("/api/topics", {
      data: { id: TOPIC, name: "E2E Topic", scope_statement: "llm agents for e2e testing" },
    });
  }
});

test("F4: topics list opens and shows the seeded topic", async ({ page }) => {
  await page.goto("/topics");
  await expect(page.getByRole("heading", { name: "Topics" })).toBeVisible();
  await expect(page.getByText("e2e-topic")).toBeVisible();
});

test("F2/F3: three routes support direct deep links", async ({ page }) => {
  for (const path of ["/topics", `/topics/${TOPIC}`, `/topics/${TOPIC}/chat`]) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
  }
});

test("report: open an existing run, then switch Trajectory/Report", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  const firstRun = page.locator(".run-list li").first();
  await expect(firstRun).toBeVisible({ timeout: 20_000 });
  await firstRun.click();

  await page.getByRole("tab", { name: "Trajectory" }).click();
  await expect(page.locator("[data-stage]")).toHaveCount(10);

  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByText(/Claims|sha /i).first()).toBeVisible({ timeout: 20_000 });
});

test("chat: first answer cites evidence and shows tool trace", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  await page.getByPlaceholder("Ask about this topic, Enter to send").fill("tool use");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(
    page.locator(".chat-msg").filter({ hasText: "According to [E2E-P" }).last(),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Tool trace").last()).toBeVisible();
  await expect(page.locator(".chat-msg").last().locator(".el-tag")).toHaveCount(3);
});

test("chat: follow-up keeps history and refuses without evidence", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  const input = page.getByPlaceholder("Ask about this topic, Enter to send");
  await input.fill("tool use");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.locator(".chat-msg").filter({ hasText: "According to [E2E-P" }).last(),
  ).toBeVisible({ timeout: 20_000 });

  // Chinese input is intentional: the reply language should mirror the question.
  await input.fill("再具体一点");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.locator(".chat-msg").filter({ hasText: "根据 [E2E-P" }).last(),
  ).toBeVisible({ timeout: 20_000 });

  await input.fill("zzz-nonexistent");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/can't answer from this topic|no citable snippets/).last()).toBeVisible({
    timeout: 20_000,
  });
});

test("F12: health endpoint reports the current schema", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { ok: boolean; sqlite: { tables: number } };
  expect(payload.ok).toBe(true);
  expect(payload.sqlite.tables).toBe(26);
});

test("S12: trajectory shows ten stages", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  const firstRun = page.locator(".run-list li").first();
  await expect(firstRun).toBeVisible({ timeout: 20_000 });
  await firstRun.click();

  await page.getByRole("tab", { name: "Trajectory" }).click();
  await expect(page.locator("[data-stage]")).toHaveCount(10);
  for (const label of ["Intake", "Scope", "Retrieval", "Analysis", "Critique", "Report", "Evaluate"]) {
    await expect(page.getByText(label, { exact: false }).first()).toBeVisible();
  }
});

test("S12: report renders real sections", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  const firstRun = page.locator(".run-list li").first();
  if (await firstRun.count()) await firstRun.click();
  await expect(page.getByRole("tab", { name: "Report" })).toBeVisible();
  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByText(/Overview|Findings|Claims/i).first()).toBeVisible({ timeout: 20_000 });
});

test("S8: citation opens a paper tab and keeps Report", async ({ page, request }) => {
  const runId = (await findReportRun(request)) ?? (await generateRun(request));
  await page.goto(`/topics/${TOPIC}/runs/${runId}`);
  await page.getByRole("tab", { name: "Report" }).click();

  const cite = page.locator(".cite-chip").first();
  await expect(cite).toBeVisible({ timeout: 20_000 });
  await cite.click();
  await expect(page.getByRole("tab", { name: /E2E-P\d/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Report" })).toBeVisible();
});

test("S9: intervention endpoints are implemented", async ({ request }) => {
  const runs = await request.get(`/api/topics/${TOPIC}/runs?limit=1`);
  const payload = (await runs.json()) as { items: RunItem[] };
  const run = payload.items[0];
  expect(run).toBeTruthy();

  const pause = await request.post(`/api/runs/${run.id}/pause`);
  expect(pause.status()).not.toBe(501);
  expect([202, 400, 404]).toContain(pause.status());

  const inject = await request.post(`/api/runs/${run.id}/inject`, { data: { prompt: "e2e hint" } });
  expect(inject.status()).not.toBe(501);
});

// ---------------------------------------------------------------------------
// Observability and frontend quality: cost/slowest, 409 inline, SSE fallback,
// failure card, error banner.
// ---------------------------------------------------------------------------

test("S6/S7: run header shows cost and slowest stage", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  await waitTopicIdle(page);

  await page.getByRole("button", { name: "Generate report" }).first().click();
  await page.getByRole("button", { name: "Start" }).click();

  const header = page.locator(".run-workspace");
  await expect(header.getByText(/\$\d+\.\d{4}/)).toBeVisible({ timeout: 30_000 });
  await expect(header.getByText(/Slowest /)).toBeVisible({ timeout: 30_000 });
});

test("S7: 409 is shown inline in the dialog", async ({ page }) => {
  await page.route("**/api/topics/*/run", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ code: "E_LOCK_HELD", message: "topic already has a running job" }),
    }),
  );

  await page.goto(`/topics/${TOPIC}`);
  await page.getByRole("button", { name: "Generate report" }).first().click();
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByText(/already has a running job|E_LOCK_HELD/).first()).toBeVisible({
    timeout: 10_000,
  });
});

test("S7: polling fallback completes when SSE is disconnected", async ({ page, request }) => {
  test.setTimeout(90_000);
  await expect
    .poll(
      async () => {
        const runs = await request.get(`/api/topics/${TOPIC}/runs?limit=1`);
        if (!runs.ok()) return "unknown";
        const body = (await runs.json()) as { items: RunItem[] };
        return body.items[0]?.state ?? "idle";
      },
      { timeout: 30_000, intervals: [500] },
    )
    .not.toBe("running");

  await page.route("**/api/runs/*/stream*", (route) => route.abort());

  const created = await request.post(`/api/topics/${TOPIC}/run`, {
    data: { focus_hint: null, wait: false },
  });
  expect(created.ok()).toBeTruthy();
  const { run_id: runId } = (await created.json()) as { run_id: string };

  await page.goto(`/topics/${TOPIC}/runs/${runId}`);
  await expect(page.locator(".run-workspace").getByText("succeeded").first()).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.getByText(/Claims|sha /i).first()).toBeVisible({ timeout: 30_000 });
});

test("S7: failed run shows the four-field card", async ({ page }) => {
  const failed = {
    id: "fail-1",
    topic_id: TOPIC,
    state: "failed",
    stage: "report",
    period: "2026-W43",
    focus_hint: null,
    scope_sha: null,
    error_code: "E_UNEXPECTED",
    next_seq: 0,
  };
  const item = {
    id: "fail-1",
    period: "2026-W43",
    state: "failed",
    stage: "report",
    focus_hint: null,
    error_code: "E_UNEXPECTED",
    started_at: null,
    finished_at: null,
    report_id: null,
    cost_usd: 0,
  };

  await page.route("**/api/runs/fail-1/events*", (route) =>
    route.fulfill({ json: { run_id: "fail-1", after_seq: 0, items: [], count: 0 } }),
  );
  await page.route("**/api/runs/fail-1/metrics", (route) =>
    route.fulfill({ status: 404, json: { code: "E_NOT_FOUND", message: "no metrics" } }),
  );
  await page.route("**/api/topics/*/runs?*", (route) =>
    route.fulfill({ json: { items: [item], count: 1 } }),
  );
  await page.route("**/api/runs/fail-1", (route) => route.fulfill({ json: failed }));

  await page.goto(`/topics/${TOPIC}`);
  await page.locator(".run-list li").first().click();

  await expect(page.getByText("This run did not succeed")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Error").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("S7: API failure shows an error banner", async ({ page }) => {
  const item = {
    id: "err-1",
    period: "2026-W43",
    state: "failed",
    stage: "report",
    focus_hint: null,
    error_code: "E_UNEXPECTED",
    started_at: null,
    finished_at: null,
    report_id: null,
    cost_usd: 0,
  };

  await page.route("**/api/topics/*/runs?*", (route) =>
    route.fulfill({ json: { items: [item], count: 1 } }),
  );
  await page.route("**/api/runs/err-1", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ code: "E_UNEXPECTED", message: "boom" }),
    }),
  );

  await page.goto(`/topics/${TOPIC}`);
  await page.locator(".run-list li").first().click();

  await expect(page.getByText(/E_UNEXPECTED: boom/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "Details" })).toBeVisible();
});

test("3.1: English UI mirrors Chinese questions", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  await page.getByRole("button", { name: /New chat/ }).click();
  const input = page.getByPlaceholder("Ask about this topic, Enter to send");

  await input.fill("zzz-nonexistent");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/can't answer from this topic/).last()).toBeVisible({
    timeout: 20_000,
  });

  // Chinese input is intentional: the reply should be in Chinese.
  await input.fill("工具使用");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/根据 \[E2E-P/).last()).toBeVisible({ timeout: 20_000 });
});

test("3.1: chat sessions switch and survive reload", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);

  await page.getByRole("button", { name: /New chat/ }).click();
  await expect(page.locator(".chat-msg")).toHaveCount(0);
  await page.getByPlaceholder("Ask about this topic, Enter to send").fill("tool use");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/According to \[E2E-P/).last()).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: /New chat/ }).click();
  await expect(page.locator(".chat-msg")).toHaveCount(0);

  await page.locator(".chat-sessions li").filter({ hasText: "tool use" }).first().click();
  await expect(page.getByText(/According to \[E2E-P/).last()).toBeVisible({ timeout: 10_000 });

  await page.reload();
  await expect(page.getByText(/According to \[E2E-P/).last()).toBeVisible({ timeout: 10_000 });
});
