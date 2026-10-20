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
