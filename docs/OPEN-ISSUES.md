# OPEN ISSUES（跨阶段待解决问题）

> **性质**：不绑定某个 Phase；随时可增删、调整优先级。
> **用途**：记录“知道要做、但当前不阻塞主线”的问题，避免遗忘。
> **关联**：Phase 3.3 处理质量问题；本文件保留产品/工程/体验类欠账。

## Phase 3.4 指标与评价体系（S16–S19）

**状态：S16 已实现；S17–S19 部分实现。**

目标不是“加一个仪表盘”，而是让后续 AI 能：

- 按阶段采集指标（search/RAG/report/chat/process）；
- 用固定数据集复跑；
- 从指标自动诊断优化方向；
- 按 baseline/candidate 对比决定晋级或回滚。

最低交付：

1. `metric_definitions` / `metric_points` / `run_spans`；
2. 每阶段 span + Report 子步骤记录；
3. 固定评估集（20/50/100 篇）；
4. `eval_run` / `eval_compare` / `experiments`；
5. 人工 rubric 与 LLM judge 校准。

**阶段**：S16 schema/采集 → S17 固定评估集 → S18 评估器 → S19 闭环。

---

## Phase 3.4 迁移遗留

### OI-016 · 删除旧 10 节点 graph（P2，open）

- `graph_runner` 仍是 API/CLI 的兼容外壳；
- 新执行应走 `workflow/`；
- 删除前需迁移所有调用点和 10 阶段回归测试。

### OI-017 · Report 节点真正 Kernel 化（P1，open）

- 当前 ReportWorkflow 的 `evidence/map/write` 是 deterministic handler；
- 尚未每个节点启动 Kernel；
- 需要拆成“节点 → Kernel → tools”，并保留 artifact/checkpoint。

---

## Phase 3.4 收尾遗留（明确未完成）

1. **Phase 3.5 S2**：API/CLI 默认 `/run` 仍走 10 节点 graph；旧 graph 未删除；新 `/report-workflow` 已可用。
2. **Report 主链路 AgentVerifier** 尚未强制启用。
3. **token 级流式 UI** 未做。
4. **真实冻结评估集**（20/50/100）未建立。
5. **自动多轮优化闭环** 只到 promotion gate。
6. **search/RAG 指标采集** 尚未接入。

---

## 优先级

| 级别 | 含义 |
|---|---|
| **P0** | 影响正确性/数据安全，尽快修 |
| **P1** | 影响核心体验/质量，当前阶段或下一阶段做 |
| **P2** | 明显但可绕过，排期做 |
| **P3** | 锦上添花/长期 |

## 状态

`open` → `in-progress` → `done` / `wontfix`

---

## 清单

### OI-001 · Venue / Source AI 自动配置（P1，**partial**）

**现状**

- topic source 需要手填 `venue_ids`；
- 空 selector 直接 `E_SRC_NO_SELECTOR`；
- 用户不知道 ACL 的 OpenAlex ID，手动配置门槛高；
- 只配 venue 会抓整个会议，和 topic 不相关。

**目标**

- 用户只输入 topic scope，AI 建议 venue 名称 + 检索 query；
- 代码用 OpenAlex 解析成真实 ID；
- 用户确认/删除/手动添加；
- 保存 provenance（ai/manual）、confidence、resolver version。

**方案**

1. LLM 只输出名称/query，**不输出 ID**：
   ```json
   {"venues":["ACL","EMNLP"],"queries":["LLM agents tool use"],"from_year":2023}
   ```
2. `resolve_venues` 调 OpenAlex `/sources?search=`；
3. 返回候选 + confidence + recent_works；
4. 前端候选 chips + “Add manually” + “Apply”；
5. `POST /api/sources/suggest`、`POST /api/sources/preview`；
6. 低置信不自动应用；高置信可一键确认。

**已实现（S1–S2）**

- `POST /api/sources/suggest`、`/preview`；
- Topic 创建页 `SourceSuggest.vue`：候选勾选、手动 ID、预览；
- 选择结果写入 `sources`；未自动应用。

**验收**

- 输入 “AI Agents” 能给出 ACL/EMNLP/NeurIPS 候选；
- 不出现 LLM 编造的 source.id；
- 用户可删改；
- 保存后 `topic_sources.selector_json` 含 `venue_ids/queries/origin`。

**关联**：Phase 3.3 M1；Settings 页面 OI-014。

---

### OI-002 · Run 删除 / 归档（P2，open）

**现状**

- 前端 run 列表没有删除入口；
- 错误/测试 run 会一直留在左栏；
- 只能直接改 DB，用户体验差。

**目标**

- 可删除单条 run（含 events/reports/claims 关联）；
- 运行中的 run 不允许硬删除；
- 保留审计能力（软删除优先）。

**方案**

1. API：`DELETE /api/runs/{id}`；
   - `running/paused` → 409；
   - 默认软删除 `runs.deleted_at` + 列表过滤；
   - 可选 `?hard=true`（管理员/CLI）。
2. UI：run 行 hover “Delete” → 二次确认；
3. 删除后自动切到下一条 run / 空态；
4. 清理 `run_events`、`reports`、`claims`（硬删时）；
5. 指标/日志保留汇总。

**验收**

- 删除成功、列表消失、刷新仍消失；
- 运行中删除被拒；
- 删除失败有明确错误码。

---

### OI-003 · 右侧 Outline / Citations 面板（P2，open）

**现状**

- 目前只有 Author 右侧面板；
- 目录在报告内部（TocNav），引用列表无独立面板；
- 长报告导航不够快。

**目标**

- 右侧可折叠：Outline / Citations / Author / Claims；
- 与当前 section 联动；
- 小屏自动隐藏。

**方案**

- `RightPanel` + tabs；
- Outline 用 scroll-spy；
- Citations 按当前 section 过滤；
- Author 复用现有 AuthorPane。

---

### OI-004 · 双 Tab 并列 / 拖拽（P3，open）

**现状**

- 单 pane，动态 Paper Tab 可切换；
- 不能同时看 Report + Paper / 两篇 Paper。

**目标**

- 拖拽 tab 到右侧形成 split；
- 或先做“Open to the right”按钮。

**方案**

- 优先 `splitpanes` + 自定义 drag；
- 复杂 dock 用 `dockview-vue` 备选；
- 需要 pane 状态模型、持久化、关闭语义。

---

### OI-005 · PDF 批注 / 划词 / OCR（P3，open）

**现状**

- `iframe` 阅读 PDF；
- 无高亮/批注/扫描件 OCR。

**目标**

- pdf.js 文本层 + 高亮；
- 扫描 PDF OCR 后备。

**备注**：先保证“能读/能下载”，批注优先级低。

---

### OI-006 · 作者/团队/主题图谱（P3，open）

**现状**

- 只做 paper–author 面板；
- 无团队检测、全局图、作者消歧。

**目标**

- 1-hop ego graph；
- 团队/实验室聚合；
- 作者消歧提示。

**备注**：图只做导航，不做主界面。

---

### OI-007 · 卡住的 running run 自动清理（P2，open）

**现状**

- 进程被杀/超时后，run 可能一直 `running`；
- 后续 run 被 partial unique index 阻塞；
- e2e 曾因此超时。

**目标**

- 启动时扫描超时 running；
- 标记 `failed/E_INTERRUPTED`；
- 前端可 abort/重跑。

**方案**

- `runs.heartbeat_at`；
- 超时阈值（如 10 分钟）；
- startup hook / CLI `runs reap`。

---

### OI-008 · 测试数据与 live 数据隔离（P1，**done**）

**现状**

- e2e 与 live 共用一个 store；
- 20 篇 live 论文进入 e2e 检索，导致 23 篇时 report 卡住；
- e2e 17/18。

**目标**

- e2e 独立 data root / 独立 DB；
- 或 e2e 只用专属 topic + 过滤；
- 不污染用户报告。

**方案**

- Playwright webServer 设 `LIT_AGENT_STORAGE__DATA_ROOT=<temp>`；
- beforeAll seed；
- 测试结束清理。

---

### OI-009 · PaperCard 缓存提交后写入（P1，**done**）

**现状**

- 报告阶段 `write_cache=False` 避免嵌套写锁；
- 结果：缓存永远不写，重复 run 重复 LLM。

**目标**

- 提交成功后写缓存；
- 不阻塞 run；
- 命中率可观测。

**已实现（S4）**

- `report_cards_json` → commit 后写；
- 失败只告警；
- 仍缺：`cache_hit_rate` 指标（见 Phase 3.3 M8）。

---

### OI-010 · LLM 成本显示 `$0.0000`（P3，open）

**现状**

- litellm 没有 DeepSeek 定价；
- UI 显示 $0；
- token 有估算，但成本不准。

**方案**

- 配置 `model_prices` 表/映射；
- 未知模型显示 `estimated`；
- 不伪造 0。

---

### OI-011 · 旧报告 metadata 迁移（P3，open）

**现状**

- 3.2 前的报告 `language/generated_by/word_count` 为 null；
- UI 可能显示空白。

**方案**

- 读取时补默认 `en/template`；
- 可选迁移脚本；
- 不重写 content。

---

### OI-012 · Chat 流式 / 断线恢复（P2，3.4）

**现状**

- Chat 非流式；
- 长回答等待；
- 无 resumable stream。

**目标**

- SSE/token streaming；
- 断线恢复；
- 引用抽屉。

**备注**：3.4 处理，不在 3.3。

---

### OI-013 · 设置页面（P2，open）

**现状**

- 语言、报告参数、源配置分散；
- 无统一 Settings UI。

**目标**

- schema-driven settings；
- 分组：Sources / Report / Models / Schedule；
- 每项显示默认值、来源（ai/manual/default）、重置。

**关联**：OI-001、OI-014。

---

### OI-014 · Source 自动同步 / 报告前 ingest（P1，open）

**现状**

- 报告只读本地 papers；
- 无自动 sync；
- 用户以为“生成报告=抓新论文”。

**目标**

- run 前可选 auto-sync；
- 或 intake 阶段执行 sync；
- 明确 `E_SRC_NO_SELECTOR`/空结果提示。

**方案**

- `report.auto_sync=true`；
- 失败降级为“仅本地数据”并标注；
- 与 Phase 3.3 M1 一起做。

---

### OI-015 · E2E live 数据下偶发卡住（P1，**done**）

**现状**

- 23 篇时 report 阶段偶发卡住；
- 单独重跑可成功；
- 需要锁/超时/隔离。

**目标**

- 10 次重复无卡死；
- 超时降级；
- 独立 store。

**关联**：OI-007、OI-008、Phase 3.3 M7。

---

## 建议排期

| 优先 | 事项 |
|---|---|
| 先做 | OI-001（venue AI）、OI-008（测试隔离）、OI-009（缓存）、OI-015（稳定性） |
| 再做 | OI-002（run 删除）、OI-007（stale run）、OI-014（auto sync） |
| 后做 | OI-003、OI-013、OI-012 |
| 长期 | OI-004、OI-005、OI-006、OI-010、OI-011 |

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-29 | 首版：venue 自动配置、run 删除、右侧面板、split、PDF、图谱、stale run、测试隔离、缓存、成本、旧报告、Chat、设置页、auto sync、e2e 稳定性 |
