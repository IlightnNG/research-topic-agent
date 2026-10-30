# Phase 3.4 · Workflow + Kernel + 指标评估（Report 完整新架构）

> **版本**：3.2.0（2026-10-30，S16–S19 指标基础设施）
> **类型**：架构重构 + 质量基础设施
> **前置**：Phase 3.3 已收尾；Phase 3.4 S1–S12 已有基础层
> **目标**：Report 脱离旧 10 节点 graph，完整跑在 Workflow + Kernel 上；同时建立可复现的指标/评估体系
> **原则**：Workflow 固定；Node 有契约；Kernel 共享；Producer/Verifier 分离；指标可复算

---

## 0. 当前状态与差距

### 已有

- `kernel/`：types、tools、context、checkpoint、bounded runtime；
- `workflow/`：spec、artifacts、runner、verifier；
- Chat 已迁到 `ChatWorkflow → Kernel`；
- Report 已拆成 `evidence → map → write`，但三个节点仍是 **deterministic handler**；
- 外层 API/CLI 仍走旧 10 节点 `graph_runner`；
- 指标/评估尚未实现。

### 必须补齐

| # | 差距 | 目标 |
|---|---|---|
| G1 | Report 节点未启动 Kernel | 每个内容生产节点通过 Kernel + Tools |
| G2 | 外层仍依赖 10 节点 graph | Report 完整走 WorkflowRunner |
| G3 | 无 token/step 级流式 | 节点/步骤/生成片段可观察 |
| G4 | 无指标 | 分阶段指标、可复算 |
| G5 | 无评估集/闭环 | 固定数据集 + baseline/candidate + 晋级 |
| G6 | 长任务恢复未接 API | node/step checkpoint + resume |

**Phase 3.4 完成的定义**：

1. 从 API/CLI 发起一次 Report，**不经过 10 节点 graph**；
2. 每个 Report Node 按契约调用 Kernel（或显式 deterministic）；
3. 节点输出经 Code Gate + 独立 Verifier；
4. 失败/中断可从 node/step checkpoint 恢复；
5. 指标落库，固定评估集可复跑；
6. 旧 graph 仅保留为兼容外壳或删除。

---

## 1. 术语（冻结）

| 术语 | 定义 |
|---|---|
| **Workflow** | 最外层、固定、版本化的节点流程；没有运行时 plan |
| **Node** | 任务单元；声明 input/output/tools/budget/postconditions |
| **Kernel** | DSH 式 Agent 运行时；内部可有 plan，但不能改 Workflow |
| **Artifact** | Node 输出物；Node 间只传引用/摘要 |
| **Producer** | Node 内生成内容的 Agent |
| **Verifier** | Node 结束后的独立验收 Agent |
| **RunShell** | 一次 run 的生命周期：prepare → workflow → finalize |
| **Metric** | 有 ID/公式/单位/版本的观测值 |

**禁止**

- 外层 Workflow 内做 plan；
- Kernel 修改 Workflow 节点；
- Verifier 与 Producer 共用推理上下文；
- Node 间传完整对话。

---

## 2. 目标架构

```text
UI / API / CLI
  ↓
RunShell
  prepare → WorkflowRunner → finalize
  ↓
Workflow（固定）
  Node A → Node B → Node C → …
  ↓
Node Executor
  input artifacts → Kernel / deterministic → output artifact
  → Code Gate → Independent Verifier → checkpoint → next
  ↓
Kernel（共享）
  agent loop / tools / context / events / stream
  / checkpoint / budget / cancel / local plan
  ↓
Domain Tools + Artifact Store + Run State
```

与 DSH 的对应：

| DSH | 本系统 |
|---|---|
| Agent loop | Kernel |
| Tool registry | Domain Tools |
| Session log / stream | Run/Node/Step events |
| Context compaction | L0–L3 + handoff |
| Checkpoint | Kernel + Workflow checkpoint |
| Subagent | Node Producer |
| Orchestrator | Workflow |
| Reviewer | Independent Verifier |

---

## 3. Report 完整新架构

### 3.1 ReportWorkflow

```text
source → evidence → map → write → finalize
```

| Node | kind | 输入 | 输出 | Kernel 工具 |
|---|---|---|---|---|
| `source` | agent | topic/scope | `papers` | source.suggest / search / preview / fetch |
| `evidence` | agent | papers | `evidence` | parse / build_card / extract_claims |
| `map` | agent | evidence | `directions` | cluster_directions / compare |
| `write` | agent | directions | `report_draft` | draft_section / validate_citations / compress |
| `finalize` | deterministic | draft | `report` | validate / commit |

- `source/evidence/map/write` 必须通过 Kernel；
- `finalize` 允许确定性（校验、commit）；
- 每个 Node 有独立 input/output schema、budget、timeout、postconditions；
- Node 间只传 artifact 引用与 handoff。

### 3.2 Report 长任务

- 单次 run 可持续数小时；
- 每 Node / 每 Step checkpoint；
- 心跳：当前 node、step、tokens、已用时间；
- 停滞检测：连续无新论文/claim、重复 query、预算耗尽；
- 用户 abort 后状态 `paused`，可 resume；
- 恢复时跳过已完成 node/step，不重复 LLM 调用。

### 3.3 事件与流式

```text
run.started / node.started / step.started
tool.called / tool.result
token.delta / section.delta
artifact.updated
verifier.verdict
checkpoint.saved
run.paused / run.resumed / run.completed
```

- 事件是 UI 与审计的唯一来源；
- 报告支持 section 级流式；Chat 支持 token 级流式；
- 事件只增字段，不新增 EventType（ADR-0006）。

### 3.4 Context

| 层 | 内容 | 跨 Node |
|---|---|---|
| L0 | topic/scope/预算/用户约束 | 永久 |
| L1 | artifact 摘要、claim ledger、方向 | 引用 |
| L2 | 当前 Node 工具结果/推理 | 仅当前 |
| L3 | 原始 LLM/工具输出 | 只存 artifact |

Node 切换：保留 L0+L1，压缩 L2，丢弃 L3。

### 3.5 Producer / Verifier

- 每个内容 Node 一个 Producer（Kernel）；
- Node 结束后：
  1. Code Gate（schema/引用/预算）；
  2. 独立 AgentVerifier（不看 Producer 推理）；
  3. accept / repair / fail；
- repair 有上限；fail 不进入下一 Node；
- Verifier 不能改 Workflow。

---

## 4. 指标与评估体系

### 4.1 目标

让后续 AI 能：

1. 跑一次 → 采集指标；
2. 对比 baseline → 找到退化模块；
3. 改参数/代码 → 重跑；
4. 根据指标决定晋级或回滚。

### 4.2 数据模型

```sql
metric_definitions(
  metric_id, version, domain, unit, direction,
  formula, target_json, owner, created_at
)

metric_points(
  id, metric_id, metric_version,
  scope, scope_id, run_id, node_id, step,
  value, numerator, denominator, sample_size,
  config_hash, prompt_version, model, dataset, ts
)

run_spans(
  trace_id, span_id, parent_span_id,
  run_id, node_id, step, name, status,
  start_ts, end_ts, duration_ms,
  attributes_json, error_code
)

experiments(
  id, name, hypothesis, config_json, config_hash,
  dataset, baseline_run_id, candidate_run_ids,
  score, hard_fail, status, created_at
)
```

规则：

- 分母为 0 → `NULL`，不写 0；
- 所有指标带 version/config_hash/prompt_version；
- 不记录 prompt 正文、论文全文、密钥；
- 指标可由 events/spans 复算。

### 4.3 指标目录

#### Search / Source

| 指标 | 目标 |
|---|---|
| `search.recall_at_k` | ≥0.8 |
| `search.precision_at_k` | ≥0.8 |
| `search.topic_relevance` | ≥0.8（人工抽检） |
| `search.duplicate_rate` | <0.1 |
| `search.freshness_days` | 按 topic |

#### RAG / Retrieval

| 指标 | 目标 |
|---|---|
| `rag.context_precision` | ≥0.7 |
| `rag.context_recall` | ≥0.8 |
| `rag.faithfulness` | ≥0.95 |
| `rag.answer_relevance` | ≥0.8 |
| `rag.citation_precision` | ≥0.95 |
| `rag.citation_coverage` | 1.0 |

#### PaperCard / Claim

| 指标 | 目标 |
|---|---|
| `card.quote_verbatim_rate` | 1.0 |
| `card.field_coverage` | 记录 |
| `claim.purity` | 1.0 |
| `claim.citation_coverage` | 1.0 |
| `claim.dedup_rate` | 记录 |

#### Cluster

| 指标 | 目标 |
|---|---|
| `cluster.count` | 3–6 |
| `cluster.coherence` | 记录/提升 |
| `cluster.outlier_rate` | <0.2 |
| `cluster.name_venue_leak` | 0 |
| `cluster.name_human_score` | ≥4 |

#### Report

| 指标 | 目标 |
|---|---|
| `report.words` | 600–1200 |
| `report.sections` | 4–6 |
| `report.coverage` | ≥0.8 |
| `report.dedup_rate` | <0.1 |
| `report.fallback_rate` | <0.05 |
| `report.thin` | 0 |
| `report.readability` | ≥4 |
| `report.actionability` | ≥4 |

#### Chat

`chat.correctness / grounding / citation_fidelity / refusal_precision / latency`

#### Process

`stage.duration_ms / retries / errors / llm.calls / tokens / cost / cache_hit / tool.calls / stagnation / resume_count`

### 4.4 评估分层

| 层 | 数据 | 频率 |
|---|---|---|
| 单元 | 构造样本 | 每次提交 |
| 离线 | 固定 topic + 金标 | 每次改动 |
| 在线/人工 | 真实 run | 每周 |

固定数据集至少 3 个 topic × 20/50/100 篇；评估集**禁止优化器修改**。

### 4.5 自动评估器

- 引用/quote：规则，100% 硬校验；
- claim purity：规则；
- topic relevance：LLM judge + 人工抽检；
- RAG 四件套：RAGAS 风格；
- cluster coherence：embedding/词面 proxy；
- readability/actionability：LLM judge + rubric。

### 4.6 AI 自优化闭环

```text
baseline → run → evaluate → diagnose
  → propose → experiment → compare → promote/revert
```

- 诊断规则映射：低指标 → 候选模块；
- 参数实验 L0 自动；代码 L2 需 patch+测试+审核；
- 晋级条件：score 提升 ≥2% 且无硬指标回退；
- 最多 N 轮/预算，防止无限优化；
- 记录 experiments。

---

## 5. 实施步骤

| 步 | 内容 | 状态 |
|---|---|---|
| S1–S9 | kernel/workflow 基础、Verifier、Chat/Report 迁移 | 已完成 |
| S10 | Report 三节点拆分 + step 事件 | 已完成 |
| S11 | 旧 graph 兼容 | 部分完成（未删除） |
| S12 | 收尾 | 已完成 |
| **S13** ✅ | Report `source/evidence` 节点 Kernel 化 | 两节点独立 Kernel + tools |
| **S14** ✅ | Report `map/write` 节点 Kernel 化 | 两节点独立 Kernel + tools |
| **S15** ◐ | Report 脱离旧 graph | 节点已 Kernel 化；API/CLI 仍走 10 节点外壳，待迁移 run 生命周期 |
| **S16** ✅ | 指标 schema + 采集 | 迁移 0009；definitions/points/spans/experiments；evaluate 自动采集 |
| **S17** ◐ | 固定评估集 + eval CLI | fixture 数据集 + eval_run/eval_compare；20/50/100 冻结集待补 |
| **S18** ◐ | 自动评估器 + 人工 rubric | RuleEvaluator/LLMJudge/rubric；人工评分未执行 |
| **S19** ◐ | 自优化闭环 + experiments | 晋级策略/实验记录/optimize CLI；自动多轮循环待做 |
| **S20** | 20/50/100 压测 + 删除旧 graph + 收尾 | 待做 |

---

## 6. 验收

| # | 判据 |
|---|---|
| H1 | API/CLI 发起 Report 不经过 10 节点 graph |
| H2 | Report 每个内容 Node 都通过 Kernel |
| H3 | Node input/output schema 生效 |
| H4 | Node 结束先 Code Gate 后 AgentVerifier |
| H5 | Node/Step checkpoint 可恢复 |
| H6 | 用户 abort 后可 resume |
| H7 | 事件流包含 node/step/tool/token |
| H8 | Report 20/50/100 篇完成或明确超时 |
| H9 | 指标 definitions/points/spans 可查 |
| H10 | 指标可复算，`NULL` 与 0 可区分 |
| H11 | 固定评估集可复跑 |
| H12 | baseline/candidate 对比可输出 |
| H13 | 优化器不能修改评估集 |
| H14 | Report 引用/claim 硬门禁 |
| H15 | Chat 质量指标独立 |
| H16 | 无 prompt/全文/密钥泄漏 |
| H17 | 旧 graph 删除或仅保留兼容入口 |
| H18 | 630+ pytest、18+ e2e 全绿 |

---

## 7. 测试

- 单元：指标公式、span、checkpoint、停滞、verifier；
- 集成：Report 全 Workflow（mock gateway）；
- 规模：20/50/100 篇；
- 故障：kill 后 resume、用户 abort、LLM 超时；
- 闭环：构造可改善/不可改善数据集，验证优化器停止；
- 人工：3 topic × 5 方向 × 5 维评分。

---

## 8. 风险

| 风险 | 缓解 |
|---|---|
| Report 节点 Kernel 化后成本上升 | 预算/批量/缓存；非必要节点 deterministic |
| 长任务卡住 | 心跳/停滞/超时/取消 |
| 指标过拟合 | held-out + 人工抽检 + 禁止改评估集 |
| 迁移破坏旧功能 | feature flag + 兼容入口 |
| 上下文污染 | L0–L3 + handoff |
| 指标太多拖慢 | 采样 + 异步写 |

---

## 9. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 3.2.0 | 2026-10-30 | S16–S19 指标基础设施：30 表、metric catalog/store、eval CLI、evaluator、promotion；636 pytest / 18 e2e |
| 3.1.0 | 2026-10-30 | S13–S14 落地：Report source/evidence/map/write 全部走 Kernel；S15 待迁移 API/CLI；630 pytest / 18 e2e |
| 3.0.0 | 2026-10-30 | 补充 Report 完整新架构、指标/评估体系、S13–S20、H1–H18 |
| 2.0.0 | 2026-10-30 | S1–S12 收尾 |
| 1.0.0 | 2026-10-30 | 首版 Workflow/Kernel 架构 |
