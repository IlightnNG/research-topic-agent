# Phase 1.2 —— 前端规范（Vue 3 + TypeScript）

> **性质**：规范性文件；前端实现以此为准。
> **版本**：**1.2.4**（2026-10-20）｜改动需升版本并在 §14 记录。
> **前置**：`verify_phase1.py --online` 13/13、`pytest` 246 例全绿、OpenAPI 可用。
> **技术栈**：Vue 3 `<script setup>` + TypeScript + Vite + Element Plus + Pinia + Vue Router + Playwright。

## 0. 目标

三个页面 —— **Topics → Report（轨迹/内容双视图）→ Chat**；**扁平组织**（无子 topic）；**运行属于报告页**；**过程与结果都可见，失败不隐藏**；**少点一次、少等一次、不打断用户**。

## 1. 五条原则

| # | 原则 | 落地 |
|---|---|---|
| P1 | 扁平 | 只有 topic 一层；无子 topic、无 focus 实体；一次 run 可带可选 `focus_hint` |
| P2 | 列表按 run，徽标按 report | 左列表每行是 run；成功显"报告"、失败显"失败"、成功但无报告显"无报告" |
| P3 | 过程优先 | 运行中默认轨迹；完成后**有条件**切报告（§2.4） |
| P4 | 契约驱动 | 只渲染 API 字段；缺字段报错，不兜底为空 |
| P5 | 错误说人话 | `E_*` → 可操作中文提示，保留 code |

### 1.1 组件复用与样式纪律（**硬规则，评审按此验收**）

> 目标：**先定主题与组件，再写页面；页面只是组件的组合**。禁止"每页各写一套 CSS"。

**分层组件库（L0→L3，只能向下依赖）**

| 层 | 内容 | 例子 |
|---|---|---|
| **L0 主题/令牌** | `src/styles/tokens.css`（CSS 变量）+ Element Plus 主题覆盖 | 颜色、间距刻度、圆角、字号、阴影、状态色 |
| **L1 原子** | 通用小组件，全站复用 | `AppButton`(封装 el-button 变体)、`StatusBadge`、`PageHeader`、`EmptyState`、`ErrorBanner`、`LoadingBlock`、`KeyValue`、`CopyButton` |
| **L2 组合** | 布局与业务无关的组合 | `TwoPaneLayout`（左列表+右主区）、`SectionCard`、`DataTable`（列定义驱动）、`DialogForm`、`TabsPanel` |
| **L3 页面** | 只做编排与数据绑定 | `TopicsView`、`TopicReportsView`、`TopicChatView` |

**七条纪律**

1. **先 L0/L1 后页面**：S4 必须先交付 tokens + ≥8 个 L1/L2 组件，否则 S6–S10 不得开工。
2. **二次法则**：同一 UI 片段出现 **≥2 次**就必须抽成组件（不必等到第三次）。
3. **页面文件 ≤200 行、组件 ≤120 行**；超出即拆分。
4. **禁止针对单一元素的裸 CSS**：不得在 `scoped` 里写 `.el-input` / `.el-table__cell` / `div > span` 这类选择器，也不得用 `!important` 强改 Element Plus。需要变体时，**给组件加 `variant` prop**，在 L1 组件内部处理一次。
5. **CSS 只允许三类**：① 使用 L0 令牌（`var(--space-3)`）；② 布局工具类（`stack`/`cluster`/`grid-auto`，写在 `styles/utilities.css`）；③ 组件内部局部样式（单组件 ≤30 行，且只作用于自身根类）。**页面级 `<style>` 块应当为空或 ≤10 行。**
6. **状态色/间距/圆角/字号只能来自令牌**：集中定义 4/8/12/16/24 间距、8/12 圆角、12/13/14/16/18/20 字号、success/warning/danger/info 四态色；不得出现魔法值（`13.5px`、`#3b82f6`）。
7. **一致性优先于个性**：三页共用同一顶栏、面包屑、卡片、状态徽标、空态、错误条；差异化只允许通过 `variant`/`size`/`tone` 三个 prop 表达。

**复用验收（可执行，进 §9）**

```powershell
# 1) 页面不应出现元素级选择器或 !important
Select-String -Path web/src/views/*.vue -Pattern '\.el-|!important|>>>|:deep\('
# 2) 页面样式块行数（目标 ≤10）
Select-String -Path web/src/views/*.vue -Pattern '^<style' -Context 0,20
# 3) L1/L2 组件存在且被 ≥2 处引用
Select-String -Path web/src -Include *.vue -Pattern 'StatusBadge|TwoPaneLayout|SectionCard|EmptyState|ErrorBanner' -List
```

## 2. 信息架构

### 2.1 资源树

```
topic (扁平)
├── runs ──可选产出──> report
└── chat_sessions ──> chat_messages
authors / papers / citations 为全局资源（topic 仅作筛选参数）
```

### 2.2 路由表

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | → `/topics` | |
| `/topics` | **Topics 页**（首页） | 列表 + 新建 |
| `/topics/:topicId` | **Report 页** | 进入后按 §2.3 自动跳到某次 run |
| `/topics/:topicId/runs/:runId` | Report 页（选中） | `?view=trajectory`（默认）或 `?view=report` |
| `/topics/:topicId/chat` | **Chat 页** | Phase 3 前为"未开放"整页态 |
| `/topics/:topicId/chat/:sessionId` | Chat 页（选中会话） | 同上 |

**硬规则**：全部可深链接、刷新不丢选中态；`runId`/`sessionId`/`view` 只从 URL 读。

### 2.3 进入与自动跳转（新增，解决"进 topic 看到空白"）

打开 `/topics/:topicId` 时：

| 最新 run 状态 | 行为 |
|---|---|
| `succeeded` | **重定向** → `/runs/:lastId?view=report`（直接看最新周报） |
| `running` / `queued` | → `/runs/:lastId?view=trajectory` |
| `failed` / `aborted` | → `/runs/:lastId?view=trajectory`（红条 + 建议动作） |
| 无 run | 停留空态：一句引导 + 主按钮"生成第一份周报" |

侧栏（左列表）视图：`/topics/:id` 只在用户点面包屑时出现，此时右栏显示"选择一份周报"。

### 2.4 自动切视图的三个条件（全满足才切）

运行完成时，仅当 ① 当前正在看**这个** run；② 用户未手动切过视图（`userPinnedView=false`）；③ 当前仍是 trajectory —— 才自动切到 `report`。否则仅在左列表该项上显"报告已就绪"提示。

### 2.5 跳转逻辑

```
/topics ─[卡片:Report]→ /topics/:id ─(§2.3 重定向)→ /runs/:runId
        └[卡片:Chat]──→ /topics/:id/chat
[+ 生成新周报] → POST /run(202) → /runs/:newId?view=trajectory
```

面包屑（固定顶栏，每级可点）：`Topics / :topicName / 2026-W40`。

## 3. 页面规格

### 3.1 Topics 页

- 卡片：`id`、`name`、status、`scope_statement`（2 行截断）、`语料 N 篇 · 报告 M 份`、按钮 **Report** / **Chat**；**卡片标题区也可点**（等同 Report）；卡片右上菜单：**重命名 / 归档**（归档=`status=archived`，列表默认折叠）。
- 新建对话框：`id`（slug 校验、唯一）、`name`、`scope_statement`（10–400 字，提示"写清研究什么、不研究什么"）、`keywords[]`、`sources[]`（不填则运行时 `ingest.skip`，需内联警告）、**`focus_hint` 不在此处**（属于 run）。
- 状态：空列表（引导文案+主按钮）、骨架屏、错误（`ErrorBanner`+重试）。

### 3.2 Report 页

```
┌ 头部：topic name · scope(截断) · 语料N · 报告M · [生成新周报] ┐
├ 左 320px：run 列表              │ 右 主区：Tabs 轨迹 | 报告 ─┐
│ run #12  2026-W40  ✅ 报告      │  轨迹：事件时间线            │
│ run #11  2026-W39  ❌ 失败      │  报告：正文 + 目录 + claims  │
└────────────────────────────────┴─────────────────────────────┘
```

**左侧列表（按 run）**

- 每项：`period`（`2026-W40`）、状态徽标、运行中显示 `stage`、耗时、成本、`focus_hint`（副标题）。
- 排序：`period` 降序 → `created_at` 降序；滚动加载更多（`limit/offset`）。
- **不跳动插入**：新 run 出现时顶部显示"↑ 1 个新任务"胶囊，点击才滚动到顶。
- 点击 → `/runs/:runId`；默认视图按 §2.3 状态映射。
- "生成新周报"对话框：仅 `focus_hint`（≤120 字，可选）+ 只读显示"沿用 topic 的源与时间窗"。**请求中按钮 disable**；遇 `E_LOCK_HELD` → **对话框内联提示，不跳转**。

#### 3.2.1 轨迹视图

数据源：`GET /runs/:id`（快照）+ `GET /runs/:id/events?after_seq=N`（分页）+ `GET /runs/:id/stream`（SSE）。

**渲染只按事件类型（禁止编造"思考"）**

| type | 展示 |
|---|---|
| `phase_change` | 阶段卡：start 计时；end 显示阶段指标（新增论文/去重/证据卡） |
| `tool_call` | 工具名 + 参数摘要（≤120 字）+ 结果或错误码（失败标红） |
| `llm_call` | 模型、token、成本、缓存命中 |
| `guard_trigger` | 守卫名 + code + 原因（黄） |
| `report_written` | "报告已生成"卡 + 跳转按钮 |
| `error` | 失败四要素（错误码/最后成功阶段/已产出/建议动作） |

**顶部固定条**：state、stage、耗时、累计成本、`scope_sha`（前 8 位）、`focus_hint`；失败时红条 + "重跑"（**预填上次 `focus_hint`**，新 run_id）。

**续传（关键）**：重连时 **先 `GET /runs/:id` 刷新快照**（state/stage/report_id），再从 `lastSeq` 续 SSE；若已终态且事件到末尾 → 收尾不建流。运行中可"暂停跟随"（不自动滚底）。

#### 3.2.2 报告视图 / 失败卡片

| `run.state` | 右栏内容 |
|---|---|
| `succeeded` 且有报告 | 报告视图（下方） |
| `succeeded` 无报告 | "无报告"卡片 + 重跑 |
| `failed` / `aborted` | **失败卡片**（四要素 + 重跑）；**不请求** `/report`（避免 404 噪音） |

报告视图：正文（左）+ 目录（右 sticky，**唯一来源 `sections[]`**，禁正则解析 MD）；`degraded` → 黄条"本次无可引用证据，降级版"；claims 表（`#`/`text`/`support`/引用数），点击展开引用（`paper_id`+片段+按 source 拼外链）；**每条 claim 有"为什么"图标** → 跳轨迹并高亮 `report` 阶段事件；显示 `content_sha`（前 8 位）+ "复制 Markdown"；切视图保留滚动位置。

### 3.3 Chat 页

**Phase 3 前**：后端 501，因此整页显示"对话功能将在 Phase 3 开放"+ 能力说明（**不显示空会话列表**、不伪造消息、输入框 `disabled` 带 tooltip）。
**Phase 3 预留**：左会话列表（标题/最后消息时间）、右消息流 + 输入框；消息支持 `citations[]`，复用报告引用组件。

## 4. 关键时序

**生成**：填 `focus_hint` → `POST /run` → **202** `{run_id}` → 跳 `/runs/:id?view=trajectory` → SSE(`after_seq=0`) → 收 `report_written` → 拉 report → 按 §2.4 条件切视图。

**刷新/重连**：`GET /runs/:id` → `GET /events?after_seq=0`（分页至末尾）→ 若 running 再建 SSE（`after_seq=lastSeq`）。

**失败**：红条 + 失败四要素 + "重跑"（新 run）。

**中止**：运行中顶部"中止"按钮 → `POST /runs/:id/abort` → 状态转 `aborted`，页面按失败卡片展示（文案区分"已中止"）。

## 5. 工程结构

```
web/
├─ index.html  vite.config.ts  tsconfig*.json  playwright.config.ts
├─ e2e/                    # §9 用例
└─ src/
   ├─ main.ts  App.vue  router/index.ts
   ├─ api/{client.ts, types.gen.ts, endpoints.ts}
   ├─ stores/{topics.ts, runs.ts, chat.ts}
   ├─ composables/{useSse.ts, useRunPolling.ts}
   ├─ views/{TopicsView.vue, TopicReportsView.vue, TopicChatView.vue}
   └─ components/{TopicCard, CreateTopicDialog, GenerateReportDialog, RunList, StatusBadge,
                  TrajectoryTimeline, EventCard, ReportViewer, TocNav, ClaimTable,
                  FailureCard, EmptyState, ErrorBanner}.vue
```

约束：组件不含业务规则；API 只在 `endpoints.ts` 出现；`npm run gen:types` 由 OpenAPI 生成类型。

## 6. 状态约定

| store | 关键状态 |
|---|---|
| `topics` | `items/current/counts`（缓存 60s） |
| `runs` | `items`、`current`、`eventsBySeq: Map<seq,Event>`（**只增不重排**）、`lastSeq`、`streaming`、`userPinnedView` |
| `chat` | `sessions/messages/disabledReason`（501 → `E_FEATURE_DISABLED`） |

## 7. 后端增量（B1–B10）

| # | 增量 | 现状 → 要求 |
|---|---|---|
| B1 | `POST /topics/{id}/run` | 同步 200 → **202** `{run_id}`，后台执行 |
| B2 | `GET /topics/{id}/runs?limit&offset` | 新增；含 `period/state/stage/cost_usd/report_id/focus_hint` |
| B3 | `runs.focus_hint`、`runs.scope_sha`、**`runs.period`** | 新增三列（period 由 created_at 所在 ISO 周计算） |
| B4 | `report.sections[]` | 新增 `[{id,title,body,claim_ids}]`（TOC 唯一来源） |
| B5 | `POST /runs/{id}/abort` | **真实现**（置 aborted + 阶段间退出） |
| B6 | `POST /runs/{id}/pause|resume|inject` | 先 **501**，UI 放灰按钮 |
| B7 | `PATCH /topics/{id}` | 新增（name/scope/status=archived） |
| B8 | `GET /sources` | 已有，用于表单下拉提示 |
| B9 | `npm run gen:types` | 新增（OpenAPI → `types.gen.ts`） |
| B10 | 失败 run 的 `/report` | 返回 404 + `E_NOT_FOUND`（前端据此回落失败卡片） |

## 8. 视觉与可用性

- 左列 320px 固定；最小 1024px；不做移动端。
- 状态色：running 蓝/ succeeded 绿 / failed 红 / aborted 灰 / degraded 黄；**颜色+文字双编码**。
- 空状态必有一句"下一步做什么"+ 主按钮；首屏骨架屏；局部 spinner，禁整页白屏。
- 时间本地时区 + ISO 周并存；`Esc` 关对话框；`aria-live` 播报状态变化；Tab 可达。
- 错误码人话映射（内置）：`E_LOCK_HELD`→该 topic 已有任务在运行；`E_SRC_NO_SELECTOR`→未配置数据源；`E_SRC_AUTH`→配额/密钥问题；`E_NOT_FOUND`→资源不存在；`E_FEATURE_DISABLED`→功能未开放；`E_BUDGET_COST`→预算用尽；`E_CONFIG_INVALID`→参数不合法。

## 9. 出口标准

| # | 判据 | 方法 |
|---|---|---|
| F1 | 类型 + 构建 | `cd web && npm run typecheck && npm run build` → 0 error |
| F2 | 三路由直达 | 刷新 `/topics`、`/topics/:id`、`/topics/:id/chat` 均 200 |
| F3 | 深链接 | `/topics/:id/runs/:runId?view=report` 直达该报告 |
| F4 | **自动落最新报告** | 打开 `/topics/:id` → 落在最新 `view=report`（§2.3） |
| F5 | **不打断** | 阅读旧 run 时新 run 完成 → **不切视图**（§2.4） |
| F6 | **列表按周** | 显示 `2026-W40` 且排序正确（依赖 B3） |
| F7 | **失败卡片** | 点开失败 run → 失败四要素，无 404 红条 |
| F8 | **重连一致** | 断线 30s 重连后状态与库一致（先快照后续流） |
| F9 | **重复点击** | 连点生成 → 第二次内联 `E_LOCK_HELD`，不跳转 |
| F10 | e2e 主路径 | 建 topic → 生成 → 轨迹→报告 → 失败→重跑（Playwright） |
| F11 | 无伪造 | 轨迹仅渲染事件类型表内卡片；代码无"生成思考文本"兜底 |
| F12 | 基线不回归 | `verify_phase1.py --online` 仍 13/13 |
| F13 | **组件复用与样式纪律** | `views/*.vue` 中无 `.el-`/`!important`/`:deep(`；页面 `<style>` ≤10 行；每个页面文件 ≤200 行；L1/L2 组件 ≥8 个且各被 ≥2 处引用；无魔法色值/字号（`grep -E '#[0-9a-f]{6}' views` 为空） |

## 10. 明确不做

移动端、深色主题/品牌、多用户与鉴权、拖拽与批量、图表可视化（P5）、i18n、`pause/resume/inject`（501 占位）。

## 11. 交付物

1. `web/`（§5 结构）+ `web/e2e/`（4–5 条）
2. `docs/api/openapi.json` 刷新 + `web/src/api/types.gen.ts`
3. 后端 B1–B7 实现（B8 已有、B9 脚本、B10 语义）
4. `docs/implementation/RESULTS-P1.2.md`（构建结果、e2e 记录、截图）

## 12. 实施步骤（S1–S11）

> **结论：Phase 1.2 不能在一次对话内完成。** 它是 5–7 人日、约 25–30 个文件、含 npm 安装与 TS 类型迭代的工程，
> 且每步都需要"改 → 构建/测试 → 修"的循环。**一次对话最多覆盖 2–3 步**（见 §14 分批建议）。

**依赖顺序**：S1 → S2 → S3 是后端（S2/S3 可并行）；S4 → S5 是前端骨架；S6–S10 是页面（S6 与 S7 可并行，但都依赖 S5）；
S11 收口（依赖全部）。

| 步 | 内容 | 预估 | 可回滚点 |
|---|---|---|---|
| **S1** | 后端契约：`runs.period/focus_hint/scope_sha` 三列 + 迁移 + `GET /topics/{id}/runs` + `PATCH /topics/{id}` | 0.5 d | 迁移可 downgrade；端点可摘除 |
| **S2** | 异步 run：`POST /run` → 202 + 后台执行 + `POST /runs/{id}/abort`（真实现） + `pause/resume/inject` 501 | 1.0 d | 保留 `?sync=true` 回退开关 |
| **S3** | `report.sections[]`：reporter 产出分节 + API 返回 + 失败 run 的 `/report` 返回 404 `E_NOT_FOUND` | 0.5 d | 字段可空，前端兼容 `content_md` |
| **S4** ✅ | 已完成：TS 工程 + tokens/utilities + 15 个组件 + 5 条路由；`npm run typecheck` 0 error、`npm run build` 通过 | 0.75 d | 旧版备份在 `web/src/legacy/` |
| **S5** ✅ | 已完成：`client/types/endpoints` + `stores/{topics,runs}` + `useSse`（断线指数重连）；类型为手写（`types.gen` 待接） | 0.5 d | 纯新增文件 |
| **S6** ✅ | 已完成：卡片网格 + 新建校验（slug/scope）+ 归档菜单 + 计数 + 骨架/空态/错误 | 0.5 d | 单页回退 |
| **S7** ✅ | 已完成：run 列表（period/徽标/成本）+ 返回链接 + §2.3 自动落最新 + §2.4 不打断 + 生成对话框 409 内联 + 中止；列表胶囊未做 | 1.0 d | 页面可独立回退 |
| **S8** ✅ | 已提前完成：时间线（阶段/严重级/摘要）+ 跟随开关 + 失败卡片 + 中止 | 1.0 d | 只影响右栏 |
| **S9** ✅ | 已提前完成：正文 + 目录（sections 派生）+ claims 表 + degraded 黄条 + 复制 MD + claim→轨迹 | 0.5 d | 只影响右栏 |
| **S10** | Chat 501 整页态、错误码人话映射、空态/骨架/aria、1024px 布局收尾 | 0.5 d | 单页回退 |
| **S11** | Playwright e2e（F4–F10）+ `RESULTS-P1.2.md` + 基线回归 + 构建产物 | 1.0 d | 仅新增测试/文档 |

### 每步通用门禁（缺一即不得进下一步）

| 层 | 命令 | 期望 |
|---|---|---|
| 后端 | `uv run pytest -q` / `uv run ruff check .` | 全绿 / clean |
| 后端 | `uv run python scripts/verify_phase1.py --online` | 仍 **13/13** |
| 前端 | `cd web && npm run typecheck && npm run build` | 0 error |
| 前端 | 手动清单（该步涉及页面） | 按该步"验收"逐条打勾 |
| 文档 | 本文件 §12 该步追加一行完成记录 | 有日期与证据 |

### 分步验收要点（逐条可测）

- **S1**：`GET /api/topics/{id}/runs` 返回 `period` 且排序正确；`PATCH` 改 `name/status` 生效；`pytest -k "runs_list or topic_patch"` 绿。
- **S2**：`POST /run` 立刻返回 202 且 `run_id` 可查；并发同 topic → 409；`abort` 后状态 `aborted` 且事件停止增长；`pytest -k "async_run or abort"` 绿。
- **S3**：`/report` 含 `sections[]`，其 `claim_ids` 与 `claims[]` 一致；失败 run 的 `/report` → 404 `E_NOT_FOUND`。
- **S4**：`npm run typecheck` 通过；三路由空壳可导航、刷新不 404。
- **S5**：`runs` store 的 `eventsBySeq` 对重复 seq **不新增行**（可用两条相同事件手测）。
- **S6**：建 topic 校验拦截非法 slug；归档后列表默认折叠；计数显示 `0/0`。
- **S7**：F4 自动落最新报告；F5 不打断；F6 列表按周；F9 连点内联 `E_LOCK_HELD`。
- **S8**：F7 失败卡片；F8 断线 30s 后状态与库一致；"中止"按钮可用。
- **S9**：TOC 由 `sections[]` 生成；`degraded` 显示黄条；claim→轨迹高亮 `report` 阶段；复制 MD 内容与 `content_md` 一致。
- **S10**：Chat 显示"未开放"且无空列表；错误码映射表生效（注入 404/409/501 各一次）。
- **S11**：F1–F12 全部可执行并记录；`RESULTS-P1.2.md` 含构建体积、e2e 截图、基线 13/13。

## 13. 对话分批建议（给执行用）

| 批次 | 步骤 | 预计对话轮次 | 说明 |
|---|---|---|---|
| **批 1（后端）** | S1 → S2 → S3 | 3–4 轮 | 全部可离线测，风险最低，先把契约稳定 |
| **批 2（前端骨架 + 两页）** | S4 → S5 → S6 → S7 | 4–5 轮 | 一次性把"能点进去"打通 |
| **批 3（双视图 + 收尾 + e2e）** | S8 → S9 → S10 → S11 | 4–6 轮 | 交互细节最多，留足返工余量 |

> 每轮对话只做**一个 S**，结束时必须输出：`门禁结果 + 新增/修改文件清单 + 一句英文 commit`。

## 14. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.2.0 | 2026-10-20 | 首版：三页 IA、run-as-list-item、双视图、扁平 topic + run 级 `focus_hint` |
| **1.2.4** | 2026-10-20 | S4–S9 已实现并实测（typecheck 0 error、build 通过；详见 `RESULTS-P1.2.md`）；S10/S11 待做 |
| **1.2.3** | 2026-10-20 | 新增 **§1.1 组件复用与样式纪律**（L0–L3 分层、七条纪律、二次法则、页面 ≤200 行/组件 ≤120 行、禁裸 CSS 与 `!important`、CSS 仅三类、状态色/间距/字号只能来自令牌）；S4 改为"先交付 tokens + ≥8 个 L1/L2 组件再写页面"（0.5→0.75 d）；新增出口判据 **F13 组件复用与样式纪律**（含 grep 检查）
