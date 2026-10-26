import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const TOPIC = "e2e-topic";

/** 等上一条 run 结束，避免"topic 已锁"导致后续生成 409。 */
async function waitTopicIdle(page: Page): Promise<void> {
  const first = page.locator(".run-list li").first();
  if (await first.count()) {
    await expect(first).not.toContainText("running", { timeout: 60_000 });
  }
}

test.beforeAll(async ({ request }) => {
  // 幂等准备：topic 已存在则忽略 400/409（PATCH/POST 由后端判重）
  const listed = await request.get("/api/topics");
  const items = (await listed.json()) as Array<{ id: string }>;
  if (!items.some((item) => item.id === TOPIC)) {
    await request.post("/api/topics", {
      data: { id: TOPIC, name: "E2E Topic", scope_statement: "llm agents for e2e testing" },
    });
  }
});

test("F4: topics 列表可打开并可新建 topic", async ({ page }) => {
  await page.goto("/topics");
  await expect(page.getByRole("heading", { name: "Topics" })).toBeVisible();
  await expect(page.getByText("e2e-topic")).toBeVisible();
});

test("F2/F3: 三条路由可直接深链访问", async ({ page }) => {
  for (const path of ["/topics", `/topics/${TOPIC}`, `/topics/${TOPIC}/chat`]) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
  }
});

test("生成周报 → 轨迹 → 报告（稳定路径：打开已有 run）", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);

  // 打开列表里第一条 run（避免与"正在运行"的自动切换竞争）
  const firstRun = page.locator(".run-list li").first();
  await expect(firstRun).toBeVisible({ timeout: 30_000 });
  await firstRun.click();

  await page.getByRole("tab", { name: "轨迹" }).click();
  await expect(page.locator("[data-stage]")).toHaveCount(10);

  await page.getByRole("tab", { name: "报告" }).click();
  await expect(page.getByText(/Claims|sha /i).first()).toBeVisible({ timeout: 30_000 });
});

test("3.3: Chat 首轮回答带引用 + 工具轨迹", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  await page.getByPlaceholder("Ask about this topic, Enter to send").fill("tool use");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(
    page.locator(".chat-msg").filter({ hasText: "根据 [E2E-P" }).last(),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Tool trace").last()).toBeVisible();
  await expect(page.locator(".chat-msg").last().locator(".el-tag")).toHaveCount(3);
});

test("3.3: Chat 追问保持会话 + 无证据拒答", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  const input = page.getByPlaceholder("Ask about this topic, Enter to send");
  await input.fill("tool use");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.locator(".chat-msg").filter({ hasText: "根据 [E2E-P" }).last(),
  ).toBeVisible({ timeout: 30_000 });

  await input.fill("再具体一点");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.locator(".chat-msg").filter({ hasText: "根据 [E2E-P" }).last(),
  ).toBeVisible({ timeout: 30_000 });

  await input.fill("zzz-nonexistent");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/can't answer from this topic|no citable snippets/).last()).toBeVisible({ timeout: 30_000 });
});

test("F12: 基线健康检查可用", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { ok: boolean; sqlite: { tables: number } };
  expect(payload.ok).toBe(true);
  expect(payload.sqlite.tables).toBe(24);
});


test("S12: 轨迹展示十个阶段（含未开始）", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  const firstRun = page.locator(".run-list li").first();
  await expect(firstRun).toBeVisible({ timeout: 30_000 });
  await firstRun.click();

  await page.getByRole("tab", { name: "轨迹" }).click();
  await expect(page.locator("[data-stage]")).toHaveCount(10);
  for (const label of ["接入", "界定", "检索", "分析", "自查", "成文", "评测"]) {
    await expect(page.getByText(label, { exact: false }).first()).toBeVisible();
  }
});

test("S12: 报告按真实分节渲染", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  // 打开最近一次 run（若有），再切到报告页
  const firstRun = page.locator(".run-list li").first();
  if (await firstRun.count()) await firstRun.click();
  await expect(page.getByRole("tab", { name: "报告" })).toBeVisible();
  await page.getByRole("tab", { name: "报告" }).click();
  // 新报告由 claims 分组落库（Findings N）；旧数据回落 Claims 表
  await expect(page.getByText(/Findings|Claims/i).first()).toBeVisible({ timeout: 30_000 });
});

test("S9: 干预端点已实装（不再是 501）", async ({ request }) => {
  const runs = await request.get(`/api/topics/${TOPIC}/runs?limit=1`);
  const payload = (await runs.json()) as { items: Array<{ id: string; state: string }> };
  const run = payload.items[0];
  expect(run).toBeTruthy();

  const pause = await request.post(`/api/runs/${run.id}/pause`);
  expect(pause.status()).not.toBe(501);
  expect([202, 400, 404]).toContain(pause.status());

  const inject = await request.post(`/api/runs/${run.id}/inject`, { data: { prompt: "e2e hint" } });
  expect(inject.status()).not.toBe(501);
});


// ---------------------------------------------------------------------------
// S6/S7：可观测与前端质量（成本/最慢阶段、409 内联、SSE 断线、失败卡、错误条）
// ---------------------------------------------------------------------------

test("S6/S7: run 头部显示成本与最慢阶段", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  await waitTopicIdle(page);

  await page.getByRole("button", { name: "生成新周报" }).first().click();
  await page.getByRole("button", { name: "开始生成" }).click();

  const header = page.locator(".run-workspace");
  await expect(header.getByText(/\$\d+\.\d{4}/)).toBeVisible({ timeout: 60_000 });
  await expect(header.getByText(/最慢 /)).toBeVisible({ timeout: 60_000 });
});

test("S7: 409 在对话框内联提示（E_LOCK_HELD）", async ({ page }) => {
  await page.route("**/api/topics/*/run", (route) =>
    route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ code: "E_LOCK_HELD", message: "该 topic 已有任务在运行" }),
    }),
  );

  await page.goto(`/topics/${TOPIC}`);
  await page.getByRole("button", { name: "生成新周报" }).first().click();
  await page.getByRole("button", { name: "开始生成" }).click();
  await expect(page.getByText(/E_LOCK_HELD|已有任务在运行/).first()).toBeVisible({ timeout: 15_000 });
});

test("S7: SSE 断开时轮询兜底仍能完成", async ({ page, request }) => {
  // 先等 topic 空闲（避免 API 触发撞锁）
  for (let i = 0; i < 60; i += 1) {
    const pageRes = await request.get(`/api/topics/${TOPIC}/runs?limit=1`);
    const body = (await pageRes.json()) as { items: Array<{ state: string }> };
    if (!body.items[0] || body.items[0].state !== "running") break;
    await page.waitForTimeout(1000);
  }

  // SSE 在任何页面加载前就被断开
  await page.route("**/api/runs/*/stream*", (route) => route.abort());

  const created = await request.post(`/api/topics/${TOPIC}/run`, {
    data: { focus_hint: null, wait: false },
  });
  expect(created.ok()).toBeTruthy();
  const { run_id: runId } = (await created.json()) as { run_id: string };

  await page.goto(`/topics/${TOPIC}/runs/${runId}`);
  await expect(page.locator(".run-workspace").getByText("succeeded").first()).toBeVisible({
    timeout: 90_000,
  });
  await page.getByRole("tab", { name: "报告" }).click();
  await expect(page.getByText(/Claims|sha /i).first()).toBeVisible({ timeout: 90_000 });
});

test("S7: 失败运行显示四要素卡片", async ({ page }) => {
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

  await expect(page.getByText("本次运行未成功")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("错误码").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "重跑" })).toBeVisible();
});

test("S7: API 失败时显示错误条并可重试", async ({ page }) => {
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

  await expect(page.getByText(/E_UNEXPECTED: boom/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "详情" })).toBeVisible();
});


test("3.1: 语言切换（默认英文，可切中文）", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  const input = page.getByPlaceholder("Ask about this topic, Enter to send");

  await input.fill("zzz-nonexistent");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/can't answer from this topic/).last()).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Switch to Chinese" }).click();
  await expect(page.getByText(/无法从本 topic 的证据回答/).last()).toBeVisible();

  await page.getByRole("button", { name: "Switch to English" }).click();
  await expect(page.getByText(/can't answer from this topic/).last()).toBeVisible();
});

test("3.1: 会话列表可切换", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  await page.getByRole("button", { name: /New chat/ }).click();
  await expect(page.locator(".chat-msg")).toHaveCount(0);

  await page.locator(".chat-sessions li").nth(1).click();
  await expect(page.locator(".chat-msg").first()).toBeVisible({ timeout: 15_000 });
});
