# Phase 3.5 · 全量新架构切换与科研级 Report

> **版本**：1.2.0（2026-10-31，S4–S6 基础落地）
> **目标**：完成 Workflow + Kernel 全量切换；让 Report 能基于约 100 篇论文生成**详细、准确、可引用、可用于研究**的报告；评估体系完整可优化
> **前置**：Phase 3.4 收尾（640 pytest / 18 e2e；Report 4 节点已 Kernel 化；指标基础表已建）
> **非目标**：多用户权限、云端部署、PDF 批注（保持 OPEN-ISSUES）
> **原则**：先完成架构切换，再追求报告质量；所有质量提升必须有指标和验收，不靠“看起来更长”

---

## 0. 当前基线（Phase 3.4 收尾后）

### 已有

- `kernel/`：tools、context、checkpoint、bounded loop、budget/cancel/no_progress；
- `workflow/`：固定 spec、artifact、runner、CodeVerifier、AgentVerifier；
- Chat：ChatWorkflow → Kernel；
- Report：`source → evidence → map → write` 每个节点通过 Kernel + tool；
- 指标表：`metric_definitions / metric_points / run_spans / experiments`（30 表）；
- eval CLI、规则评估、promotion gate 基础；
- 640 pytest、18 e2e。

### 必须解决

| # | 问题 | 影响 |
|---|---|---|
| P1 | API/CLI 仍包在旧 10 节点 graph 外壳 | 不是全量新架构 |
| P2 | 旧 graph 未删除 | 两套流程并存 |
| P3 | Report 只在小规模/词面检索上验证 | 100 篇不可用 |
| P4 | 方向聚类仍偏词面 | 方向粗、噪声 |
| P5 | 无真实 100 篇冻结评估集 | 指标不可信 |
| P6 | AgentVerifier 未强制接入主链路 | 验收不完整 |
| P7 | token/section 流式 UI 未做 | 长任务不可观察 |
| P8 | 自动优化只到 promotion gate | 未闭环 |
| P9 | search/RAG 指标未接入 | 评估不完整 |

**Phase 3.5 完成的定义**：

1. API/CLI 的 Report **不再经过 10 节点 graph**；
2. 旧 graph 删除或仅保留离线兼容模块；
3. 100 篇真实论文可生成研究级报告；
4. 每个节点有 Producer + Code Gate + Independent Verifier；
5. 指标覆盖搜索/RAG/claim/cluster/report/process；
6. 固定 100 篇评估集可复跑，指标可驱动参数优化；
7. 中断/恢复/停滞可观察。

---

## 1. 目标架构（最终形态）

```text
UI / API / CLI
  ↓
RunShell（新，替代 10 节点 graph）
  prepare → WorkflowRunner → evaluate → finalize
  ↓
Workflow（固定）
  Report: source → evidence → map → write → finalize
  Chat:   answer → finalize
  ↓
Node Executor
  input artifacts → Kernel → tool calls
  → Code Gate → AgentVerifier → checkpoint → next
  ↓
Kernel（共享）
  agent loop / tools / context / events / stream
  / checkpoint / budget / cancel / local plan
  ↓
Domain Tools + Artifact Store + Run State + Metrics
```

### 1.1 RunShell

替代旧 `graph_runner`：

```text
prepare_run（锁/run 行/预算）
  → WorkflowRunner
  → evaluate（指标/门禁）
  → finalize（两阶段提交/事件）
  → resume / abort / pause
```

- API `/run`、CLI `run-topic` 都走 RunShell；
- 旧 10 阶段事件仅作为兼容层，**不再执行旧节点**；
- 前端 Trajectory 改为 Workflow Node 视图，保留旧视图开关一个版本。

### 1.2 Workflow 节点

| Workflow | 节点 |
|---|---|
| Report | source → evidence → map → write → finalize |
| Chat | answer → finalize |

每个 Node：

- `kind: deterministic | agent`；
- input/output schema；
- allowed_tools、budget、timeout、postconditions；
- checkpoint；
- Code Gate + Verifier。

### 1.3 Kernel

- 共享，不包含领域 workflow 决策；
- 内部 plan 只拆当前 Node；
- token/step 事件；
- 工具白名单；
- 断点恢复。

### 1.4 Producer / Verifier

- 每个内容 Node：Producer Kernel + 独立 Verifier Agent；
- Verifier 只看 artifact + contract + evidence；
- 输出 `accept / repair / fail`；
- repair 有上限，fail 不进入下一 Node；
- Verifier 不能改 Workflow。

---

## 2. Report 100 篇科研级方案

### 2.1 目标输出

一份报告包含：

```text
1. At a Glance
   - 论文数、方向数、必读 3 篇、覆盖/证据质量
2. Direction Map
   - 5–8 个方向，每个方向 ≥3 篇
3. Deep Dives
   - 每方向：共同点、差异、代表论文、方法/数据/评测
4. Comparison Matrix
   - 方向 × 问题/方法/数据/指标/结论
5. Cross-cutting Themes
   - 共用方法、数据集、评测、理论工具
6. Contradictions & Gaps
   - 相互矛盾、单篇支持、证据缺口
7. Paper Index
   - 100 篇论文的可点击索引
8. Method & Coverage
   - 检索式、时间窗、全文覆盖、限制
```

### 2.2 规模目标

| 指标 | 100 篇目标 |
|---|---|
| 论文覆盖 | ≥80 篇有 claim |
| claims | 120–200 条（每篇 1–2 条） |
| 方向 | 5–8 个；每方向 ≥3 篇 |
| 报告字数 | 1500–3000 words |
| 引用覆盖 | 100% |
| fallback | <2% |
| 报告生成时间 | 30–90 分钟（可配置） |
| 成本 | 预算上限内 |

### 2.3 分层阅读

不能 100 篇全部精读：

| 层 | 范围 | 目的 |
|---|---|---|
| L1 | 100% | 元数据 + 摘要 + 结构化略读 |
| L2 | 30–40% | 代表/争议/高相关论文精读 |
| L3 | 按 claim | quote 窗口核验 |

参数：

```yaml
report:
  deep_read_ratio: 0.35
  max_chunks_per_paper: 4
  max_claims_per_paper: 2
  token_budget: 500000
  step_timeout_s: 600
```

### 2.4 检索与源

- source 节点支持 query + venue + date；
- 抓取后做 relevance 过滤，保留约 100 篇；
- 记录检索式、时间窗、来源覆盖率；
- 不足 100 篇时明确 `coverage_deficit`，不假装完整；
- 预抓取与缓存，避免重复下载。

### 2.5 Claim 与证据

- 每篇 1–2 条 research claim；
- 必须 quote 原文 + page/section；
- 书目/作者 claim 拒绝；
- 跨论文去重；
- claim_id 稳定；
- unsupported 保留并标注，不伪造 grounding。

### 2.6 聚类

- 优先 embedding + HDBSCAN/层次聚类；
- 无 embedding 时 TF-IDF + cosine，词面 Jaccard 仅兜底；
- 去 venue/出版/作者 boilerplate；
- `min_cluster_size=3`（100 篇场景）；
- 方向命名：LLM 仅基于 cluster 内 claims，禁止外部论文；
- 记录 coherence/outlier/version。

### 2.7 写作

- 先 outline，再 section；
- 每 section 必须引用 claim；
- 对比矩阵由代码构建，LLM 只写对比文字；
- 每个方向必须有：
  - common ground（≥2 篇）
  - differences（≥2 篇）
  - open questions
- 无证据段落丢弃；
- 语言 en/zh，引用不变。

### 2.8 验收与修复

- Code Gate：schema、引用、quote、claim 数、方向最小规模；
- AgentVerifier：相关性、可读性、对比深度、是否有未支持断言；
- repair 上限 2 次；
- fail → 该方向降级或整体模板回落，不无限循环。

---

## 3. 评估体系（完整）

### 3.1 数据模型

已有表：

```text
metric_definitions / metric_points / run_spans / experiments
```

Phase 3.5 补齐：

- `metric_definitions`：每个指标必须有公式/单位/方向/目标；
- `metric_points`：node_id/step/config_hash/prompt_version；
- `run_spans`：每个 Node/Step/Tool 一个 span；
- `experiments`：baseline/candidate/score/hard_fail。

### 3.2 指标目录

#### Search

| 指标 | 目标 |
|---|---|
| `search.recall_at_20` | ≥0.8 |
| `search.precision_at_20` | ≥0.8 |
| `search.topic_relevance` | ≥0.8 |
| `search.coverage` | 80–120 篇 |
| `search.duplicate_rate` | <0.1 |

#### RAG

| 指标 | 目标 |
|---|---|
| `rag.context_precision` | ≥0.7 |
| `rag.context_recall` | ≥0.8 |
| `rag.faithfulness` | ≥0.95 |
| `rag.citation_precision` | ≥0.95 |
| `rag.citation_coverage` | 1.0 |

#### Claim / Card

| 指标 | 目标 |
|---|---|
| `card.quote_verbatim_rate` | 1.0 |
| `claim.purity` | 1.0 |
| `claim.citation_coverage` | 1.0 |
| `claim.count` | 120–200 |
| `claim.duplicate_rate` | <0.1 |

#### Cluster

| 指标 | 目标 |
|---|---|
| `cluster.count` | 5–8 |
| `cluster.min_size` | ≥3 |
| `cluster.coherence` | 记录/提升 |
| `cluster.outlier_rate` | <0.2 |
| `cluster.name_venue_leak` | 0 |
| `cluster.name_human_score` | ≥4 |

#### Report

| 指标 | 目标 |
|---|---|
| `report.words` | 1500–3000 |
| `report.sections` | 6–8 |
| `report.coverage` | ≥0.8 |
| `report.cited_claim_ratio` | 1.0 |
| `report.fallback_rate` | <0.02 |
| `report.thin` | 0 |
| `report.comparison_completeness` | ≥0.8 |
| `report.readability` | ≥4 |
| `report.actionability` | ≥4 |

#### Process

| 指标 | 目标 |
|---|---|
| `stage.duration_ms` | 记录/预算 |
| `llm.calls/tokens/cost` | 记录 |
| `llm.failure_rate` | <0.05 |
| `cache_hit_rate` | 记录/提升 |
| `tool.failure_rate` | 记录 |
| `run.stagnation` | 0 |
| `resume_count` | 记录 |

### 3.3 固定数据集

```text
eval/datasets/
  ai-agents-100/
    topic.json
    papers.jsonl
    gold_claims.jsonl
    gold_directions.jsonl
    gold_report.md
    rubric.md
```

要求：

- 100 篇真实论文；
- 3 个 topic（AI Agents / RAG / Long-context）；
- 金标可版本化；
- 评估集不可被优化器修改；
- 训练/调参/测试分离。

### 3.4 评估器

| 评估器 | 方法 |
|---|---|
| 引用/quote | 规则，硬门禁 |
| claim purity | 规则 |
| topic relevance | LLM judge + 人工抽检 |
| RAG 四件套 | RAGAS 风格 |
| cluster coherence | embedding/词面 |
| readability/actionability | rubric + judge |
| 人工 | 双评审，1–5 分，一致性 |

### 3.5 参数优化

参数表：

```yaml
deep_read_ratio: [0.2, 0.35, 0.5]
max_claims_per_paper: [1, 2, 3]
cluster_threshold: [0.15, 0.2, 0.25]
min_cluster_size: [2, 3, 4]
max_tokens_synthesis: [1000, 1500, 2000]
token_budget: [300k, 500k, 800k]
```

方法：

1. 固定评估集 + 固定 seed；
2. baseline 先跑 3 次取中位数；
3. 一次一参数/小网格；
4. 记录 config_hash；
5. 选 Pareto（质量/成本/时间）；
6. 每次实验写入 `experiments`；
7. 晋级条件：score 提升 ≥2%，无硬指标回退；
8. 最多 N 轮，预算耗尽停止。

### 3.6 闭环

```text
baseline → run → evaluate → diagnose
  → propose → experiment → compare → promote/revert
```

- 诊断规则：指标 → 模块；
- 参数自动；代码改动需测试/评审；
- 评估集只读；
- 保留实验记录。

---

## 4. 实施步骤

| 步 | 内容 | 预估 |
|---|---|---|
| S1 | RunShell + API/CLI 直连 WorkflowRunner | 4d |
| S2 | 删除旧 graph 或降级为离线 adapter | 3d |
| S3 | Report source 节点：query/venue/100 篇抓取/过滤 | 4d |
| S4 | evidence：分层阅读 + 卡片 + claim | 4d |
| S5 | map：embedding/聚类 + 方向命名 | 4d |
| S6 | write：outline + deep dive + 对比矩阵 | 5d |
| S7 | Code Gate + AgentVerifier 强制接入 | 3d |
| S8 | 事件/stream（section 级）接入 UI | 4d |
| S9 | checkpoint/resume/停滞检测接入 API | 4d |
| S10 | 指标采集补全 search/RAG/cluster | 4d |
| S11 | 100 篇冻结评估集 + 金标 | 5d |
| S12 | 自动评估器 + judge 校准 + 人工 rubric | 5d |
| S13 | 参数调优 + experiments | 4d |
| S14 | 自动闭环（参数级） | 4d |
| S15 | 100 篇端到端 + 20/50 回归 | 5d |
| S16 | 收尾/文档/删除旧路径 | 3d |

**总计 ≈ 65 人日。**

---

## 5. 验收

| # | 判据 |
|---|---|
| H1 | API/CLI Report 不经过 10 节点 graph |
| H2 | 旧 graph 删除或仅离线兼容 |
| H3 | 100 篇端到端完成 |
| H4 | 报告 1500–3000 words，6–8 方向 |
| H5 | ≥80 篇有 claim；120–200 claims |
| H6 | citation coverage 1.0 |
| H7 | claim purity ≥0.98 |
| H8 | 每方向 ≥3 篇，有 common/differences |
| H9 | AgentVerifier 每 Node 执行 |
| H10 | node/step checkpoint + resume |
| H11 | 中断后可恢复，不重复 LLM |
| H12 | 停滞检测有效 |
| H13 | section 级流式可见 |
| H14 | 指标 definitions/points/spans 完整 |
| H15 | 100 篇固定集可复跑 |
| H16 | 指标可解释、NULL 与 0 分离 |
| H17 | 参数实验可复跑 |
| H18 | 优化不修改评估集 |
| H19 | 成本/时间在预算内 |
| H20 | 640+ pytest、18+ e2e 全绿 |

---

## 6. 质量门槛（100 篇）

| 维度 | 不通过条件 |
|---|---|
| 覆盖 | 有 claim 的论文 <80 |
| 方向 | 方向 <5 或 >8；存在 <3 篇方向 |
| 引用 | 任一事实段无引用；引用不可解析 |
| claim | 书目 claim；quote 非原文 |
| 对比 | 只有罗列，无 comparison matrix |
| 可读性 | 人工均分 <3.5 |
| 可复现 | 同配置两次结果不可解释 |
| 性能 | 超过预算/时间上限且无降级 |

---

## 7. 测试计划

### 7.1 单元

- Node 契约、artifact schema；
- Kernel budget/cancel/no_progress；
- context L0–L3；checkpoint；
- verifier accept/repair/fail；
- 指标公式、NULL 语义、评估器。

### 7.2 集成

- 20/50/100 篇 ReportWorkflow；
- 100 篇分层阅读；
- API/CLI 直接 RunShell；
- 事件流/恢复；
- 指标落库。

### 7.3 故障

- LLM 超时/截断；
- 数据库锁；
- 进程 kill；
- 用户 abort；
- 长时间停滞。

### 7.4 人工

- 3 topic × 5 方向 × 5 维评分；
- 两名评审，报告一致性；
- 与 baseline 对比。

---

## 8. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 100 篇成本过高 | 分层阅读、缓存、预算、Pareto |
| 报告变长但空洞 | 字数不是唯一目标；引用/对比门槛 |
| 聚类不稳 | 固定 seed/embedding 版本 |
| 自动优化过拟合 | held-out + 禁止改评估集 |
| graph 删除破坏兼容 | 先双路径，后删除 |
| 长任务卡死 | 心跳/停滞/超时/恢复 |
| 指标采集拖慢 | 异步/采样 |

---

## 9. 最终交付物

1. RunShell + WorkflowRunner 全量切换；
2. 旧 graph 删除/离线兼容；
3. 100 篇科研级 Report；
4. 指标目录 + 固定评估集 + 人工 rubric；
5. 参数优化实验记录；
6. 完整结果文档与回归。

---

## 10. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.2.0 | 2026-10-31 | S4 分层选择、S5 向量聚类、S6 对比矩阵/主题；647 pytest / 18 e2e |
| 1.1.0 | 2026-10-30 | S1 部分（新增 RunShell/API/CLI，默认 `/run` 仍走 graph）；S3 source 已完成；644 pytest / 18 e2e |
| 1.0.0 | 2026-10-30 | Phase 3.5：全量架构切换、100 篇科研报告、完整评估体系、S1–S16、H1–H20 |


---

## 11. 实施状态（2026-10-30）

| 步 | 状态 | 说明 |
|---|---|---|
| S1 | ◐ | `RunShell` + 新 API `/report-workflow` + CLI 已有；默认 `/run` 仍走旧 graph |
| S2 | ❌ | 旧 graph 未删除；不能宣称全量切换 |
| S3 | ✅ | source resolver：topic/focus/limit/100、本地排序、empty_retrieval 降级 |
| S4+ | 待做 | — |

### 新增入口

```text
POST /api/topics/{topic_id}/report-workflow
python scripts/run_report_workflow.py --topic ai-agents --limit 100
```

### 当前边界

- 新入口不经过 10 节点 graph；
- 默认 `/run` 仍是旧 graph，前端/CLI 旧路径未切；
- 因此 S1 只算“新路径可用”，不是“默认全量切换”；
- S2 未做，符合“不假装删除”。


---

## 12. S4–S6 实施状态（2026-10-31）

| 步 | 状态 | 说明 |
|---|---|---|
| S4 | ◐ | 分层证据选择（L1/L2/L3）已入 context；未接全文精读 |
| S5 | ◐ | char-ngram 向量 + cosine 聚类已接入；仍非真实 embedding/HDBSCAN |
| S6 | ◐ | 报告新增 Comparison Matrix / Cross-cutting Themes；未达 1500–3000 字科研长文 |

### 已实现

- `report/evidence.py`：`select_evidence_tiers`；
- `report/embeddings.py`：`build_directions_embedding`；
- `ReportContext` 使用向量聚类，meta 记录 tiers；
- `assemble.py`：对比矩阵、跨方向主题；
- 中英文 label 对齐。

### 仍未实现

- 真 PDF 全文精读/quote 窗口；
- 真实 embedding 模型；
- 对比矩阵的 LLM 对比文字（目前表格结构）；
- 1500–3000 字深度写作；
- 100 篇真实评估。
