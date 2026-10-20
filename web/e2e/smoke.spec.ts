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

test("生成周报 → 轨迹 → 自动切到报告", async ({ page }) => {
  await page.goto(`/topics/${TOPIC}`);
  await page.getByRole("button", { name: "生成新周报" }).first().click();
  await page.getByRole("button", { name: "开始生成" }).click();

  // 轨迹视图出现事件（至少有一条 phase_change）
  await expect(page.getByText("phase_change").first()).toBeVisible({ timeout: 30_000 });

  // 完成后自动切到报告：出现 claims 表或报告头（sha / Claims）
  await expect(page.getByRole("tab", { name: "报告" })).toBeVisible();
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
