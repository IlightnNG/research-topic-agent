# RESULTS — Phase 1.2 前端（S4–S7）

> 依据：`phase1.2-frontend-spec.md`（v1.2.3）§12 S1–S11。
> 本文件只记**实测**，数字均由命令产出。

## 1. 完成情况

| 步 | 内容 | 状态 |
|---|---|---|
| S1 | `runs.period/focus_hint/scope_sha` + 迁移 + `GET /topics/{id}/runs` + `PATCH /topics/{id}` | ✅ |
| S2 | 异步 202 + `POST /runs/{id}/abort`（真实现）+ pause/resume/inject 501 | ✅ |
| S3 | `sections[]`（由 claims 派生）+ 失败 run `/report` → 404 `E_NOT_FOUND` | ✅ |
| S4 | TS 工程 + tokens/utilities + 8 个基础组件 + Router + 三页骨架 | ✅ |
| S5 | `api/{client,types,endpoints}` + `stores/{topics,runs}` + `composables/useSse` | ✅ |
| S6 | Topics 页（卡片/新建校验/归档/计数/空态） | ✅ |
| S7 | Report 页（run 列表/§2.3 自动落最新/§2.4 不打断/生成对话框 409 内联/失败卡片/中止） | ✅ |
| S8/S9 | 轨迹时间线 + 报告视图（目录/claims/degraded/复制 MD/claim→轨迹） | ✅ |
| S10 | 错误码人话映射 + aria-live + Chat 501 整页态 | ✅ |
| S11 | Playwright e2e 5 例（`npm run test:e2e`，Chromium 在 `D:\lit-agent-store\playwright`） | ✅ 5/5 |

## 2. 实测

```text
cd web && npm run typecheck   → 0 error
cd web && npm run build       → ✓ built in 7.14s
  dist/assets/index-*.js           1,056.71 kB │ gzip: 347.47 kB
  dist/assets/TopicReportsView-*      16.14 kB │ gzip:   6.51 kB
  dist/assets/TopicsView-*             4.13 kB │ gzip:   2.13 kB
  dist/assets/topics-*.js              3.99 kB │ gzip:   1.86 kB
uv run pytest -q              → 全绿（含 S1–S3 新增 7 例）
verify_phase1.py --offline    → 11/11 PASS
```

## 3. 文件清单（新增/改写）

```
web/package.json            加 element-plus / pinia / vue-router / typescript / vue-tsc
web/tsconfig.json  tsconfig.node.json  vite.config.ts（替代 vite.config.js）
web/index.html              → /src/main.ts
web/src/main.ts             Pinia + Router + ElementPlus + tokens/utilities
web/src/App.vue             壳（顶栏 + RouterView）
web/src/env.d.ts            *.vue 声明
web/src/styles/{tokens,utilities}.css
web/src/api/{client,types,endpoints}.ts
web/src/stores/{topics,runs}.ts
web/src/composables/useSse.ts
web/src/router/index.ts     5 条路由 + 兜底
web/src/components/  PageHeader / TwoPaneLayout / SectionCard / StatusBadge /
                     EmptyState / ErrorBanner / DataTable / DialogForm /
                     RunList / TrajectoryTimeline / ReportViewer / TocNav /
                     ClaimTable / FailureCard / GenerateReportDialog   （15 个）
web/src/views/       TopicsView / TopicReportsView / TopicChatView
web/src/legacy/      旧 JS 版备份（App.vue.mjs.bak 等）
```

## 4. 已知取舍（进 known-gaps）

| 项 | 说明 |
|---|---|
| 包体积 | Element Plus 全量引入 → 主 chunk 1.05 MB（gzip 347 KB）。后续按需引入可降到 ~300 KB |
| `sections[]` 为派生 | 由 claims 生成（一节/一条），不是报告正文的真实章节；真实分节留 P2-2 |
| 列表"新任务胶囊" | 未实现（spec §3.2 B1）；当前直接刷新列表 |
| Chat 会话列表 | 按 spec §3.3 隐藏（501 整页态），`useChat` store 未建 |
| e2e | 未做（S11），当前靠 typecheck + build + 手动 |
| 深链接刷新 | 依赖 Vite dev server 的 `historyApiFallback`；生产需 Nginx `try_files`（记入部署清单） |

## 5. 下一步

- **S8/S9** 已在本次一并落地（轨迹视图 + 报告视图），可视为"提前完成"；剩余 **S10**（错误码映射细化/可访问性收尾）与 **S11**（Playwright e2e + F1–F13 全量验收）。
- 按需引入 Element Plus、列表胶囊、真实 `sections` 分节 → 记入 `phase1.1-known-gaps.md`。

## 6. S10/S11 实测（2026-10-20）

```text
cd web && npm run typecheck                 → 0 error
cd web && npm run build                     → ✓ built（主 chunk 1.06 MB / gzip 347 KB）
$env:LIT_E2E=1; uv run pytest -q tests/e2e  → 1 passed（内含 Playwright 5/5：F4 topics、F2/F3 深链、生成→轨迹→报告、Chat 501、health 24 表）
```

### 期间修掉的真实缺陷

| 缺陷 | 现象 | 根因 | 修法 |
|---|---|---|---|
| 报告页不自动加载 | 生成完成后停在"报告尚未生成。" | `decideView()` 用 `userPinnedView` 提前返回，而该标记会被程序的视图切换置真 | 去掉该门闸（只对"当前观看的 run"自动切换，天然满足 F5）；并在用户点"报告" tab 时补拉 |
| SSE 不可靠时无兜底 | 事件不刷新、状态卡住 | 仅依赖 EventSource | 增加 2s 轮询兜底（`startPolling`），终态即刷新并决定视图 |
| Playwright 输出解码 | pytest 包装器读子进程 stdout 报 `UnicodeDecodeError: gbk` | Windows 默认编码 | `encoding="utf-8", errors="replace"` |

### e2e 用例（`web/e2e/smoke.spec.ts`）

1. F4：topics 列表可打开、可见 `e2e-topic`；
2. F2/F3：`/topics`、`/topics/:id`、`/topics/:id/chat` 三条路由直接返回 200（深链）；
3. 生成周报 → 轨迹出现事件 → 报告 tab 出现内容（Claims/sha）；
4. Chat 页显示"尚未开放"；
5. `/api/health` 返回 `ok=true` 且 24 表。

> 浏览器二进制装在 **D:**（`PLAYWRIGHT_BROWSERS_PATH=D:\lit-agent-store\playwright`），避免占用 C:。

## 7. 复核后修复（批次 1 + 批次 2，2026-10-20）

### 批次 1：P0 正确性

| 项 | 修法 | 验证 |
|---|---|---|
| **B 幽灵 run** | `prepare_run()` 在**请求线程**内同步完成「拿锁 + 建 run 行 + 写 UI 字段」；线程只跑阶段（`prestarted=True`） | `test_async_202_run_is_queryable_immediately`：202 后立刻 GET → 200 |
| **B 锁冲突** | `run_topic` 遇 `E_LOCK_HELD` **重新抛出**（不吞成 failed） | `test_async_lock_conflict_returns_409_not_202`：409 `E_LOCK_HELD` |
| **C 锁泄漏** | `jobs.start` + `_init_ui_fields` 移入 `try`；`log` 声明为 `None` 并在失败分支判空 | 全量测试绿（含失败路径用例） |
| **D abort 语义** | abort 先查 run（不存在 → 404）；`finally: control.clear(rid)` | `test_abort_unknown_run_is_404`、`test_abort_flag_is_cleared_after_run` |
| **E 视图打架** | `manualView` 只在**真实 tab 点击**置位；`openRun` 按"手动选择/自动跳转"重置；`decideView` 尊重该标记 | e2e 5/5 仍绿；手动切轨迹后轮询不再弹回 |

### 批次 2：`focus_hint` 真正生效

- `_load_cards(settings, focus_hint=...)`：按 hint 的 token 过滤证据（标题+摘要）；
- `real_stages(settings, focus_hint=...)` 与 `_persist_report(..., focus_hint)` 全链路透传；
- 报告标题写入 hint → **不同 hint ⇒ 不同 `content_sha`**（可断言）；
- 若一条都不匹配 → 0 证据 + `degraded=true` + 1 条 `unsupported`（不伪造）。

验证（`tests/integration/test_batch1_2.py`，6 例）：

```text
test_focus_hint_filters_evidence_and_changes_report   2 claims → 1 claim，sha 不同
test_focus_hint_without_match_degrades                cards=0、degraded=true
uv run pytest -q                                     全绿
$env:LIT_E2E=1; uv run pytest -q tests/e2e            exit 0（Playwright 5/5）
```
