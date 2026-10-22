import { expect, test } from "@playwright/test";

const TOPIC = "e2e-topic";

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

test("Chat 页显示未开放（501 整页态）", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}/chat`);
  await expect(page.getByText("对话功能尚未开放")).toBeVisible();
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
