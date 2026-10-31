# Architecture · lit-agent v2

> 版本：1.0（2026-10-31）
> 范围：仅描述当前仓库中的 `src/lit_agent_v2/`。
> 旧 `lit_agent`、graph、report、chat、Vue 已移出仓库，不在本文范围。
> 本文同时标注“目标设计”和“当前实现”，避免把规划当成已完成。

---

## 0. 一句话架构

```text
RunShell（外层生命周期）
  → Workflow（固定节点）
  → Node（输入 artifact / 输出 artifact）
  → Kernel（节点内 ReAct 工具循环）
  → Domain Services（source/evidence/map/write/chat）
  → SQLite + Artifact Store + Metrics + Events
```

**外层 Workflow 固定，不做运行时改图。**
**内层 Kernel 是单节点的 ReAct/tool loop，不能改变 Workflow 拓扑。**

---

## 1. 设计原则

1. **固定 Workflow**
   - 节点和边在代码中声明；
   - 运行时不增加、删除、重排节点；
   - Kernel 只能拆当前节点的任务。

2. **Artifact 契约**
   - Node 之间只传 JSON artifact；
   - 不传完整对话、不传隐式全局 state；
   - artifact 内容寻址，DB 存 sha。

3. **Producer / Verifier 分离**
   - 目标：Producer 生成，独立 Verifier 审核；
   - 当前 v2 只有 CodeVerifier；AgentVerifier 尚未迁入。

4. **可恢复**
   - 每个 Node commit 后写 `run_nodes`；
   - resume 跳过 committed Node；
   - pause 在 Node 边界生效。

5. **单一入口**
   - API / CLI 只调用 `RunShell`；
   - 不允许旁路直接改 DB 或直接调 domain service 生成正式报告。

6. **无 legacy import**
   - `lit_agent_v2` 不得 import `lit_agent`；
   - 测试有 import guard。

---

## 2. 系统分层

```text
┌──────────────────────────────────────────────┐
│ API / CLI                                    │
│  api/app.py, cli.py                          │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ RunShell                                     │
│  prepare / run / pause / resume / abort      │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ WorkflowRunner                               │
│  固定 Node 顺序执行                           │
│  input artifact → handler → output artifact  │
│  CodeVerifier → commit → checkpoint          │
└──────────────────────┬───────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼────────┐          ┌─────────▼────────┐
│ Agent Node      │          │ Deterministic    │
│ Kernel + tools  │          │ handler          │
└───────┬────────┘          └─────────┬────────┘
        │                             │
┌───────▼─────────────────────────────▼────────┐
│ Domain Services                              │
│ source / evidence / map / write / persist    │
│ chat / claim extraction / openalex / pdf     │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ Storage / Observability                      │
│ SQLite, ArtifactStore, EventLog, MetricStore │
└──────────────────────────────────────────────┘
```

---

## 3. 外层 Workflow

### 3.1 Report Workflow（当前）

```text
source → evidence → map → write → finalize
```

| Node | kind（当前） | 输入 | 输出 | 说明 |
|---|---|---|---|---|
| `source` | deterministic | RunRequest | SourceArtifact | 选论文 |
| `evidence` | deterministic | SourceArtifact | EvidenceArtifact | 卡片/claim/quote |
| `map` | deterministic | EvidenceArtifact | MapArtifact | 方向聚类 |
| `write` | deterministic | Map + Evidence | ReportDraft | 章节组装 |
| `finalize` | deterministic | ReportDraft | VerifiedReport | 落库 |

**目标**：

```text
source(agent) → evidence(agent) → map(agent) → write(agent) → finalize(deterministic)
```

当前只有 Chat 真正使用 Kernel；Report 节点还是 deterministic handler。  
这是架构缺口，不是“已经完成”。

### 3.2 Chat Workflow（目标）

```text
answer → finalize
```

当前 `ChatService` 内部用 Kernel 做：

```text
search_topic → verify_claim → final
```

### 3.3 Node 契约

```python
NodeSpec(
    id: str,
    kind: "agent" | "deterministic",
    input_keys: tuple[str, ...],
    output_key: str,
    postconditions: tuple[str, ...],
    budget_usd: float,
    timeout_s: float,
    verifier: str | None,
)
```

规则：

- `input_keys` 必须由前序 Node 产出；
- `output_key` 唯一；
- commit 前过 CodeVerifier；
- commit 后写 `run_nodes(state=committed, artifact_sha=...)`；
- resume 只跳过 committed Node。

---

## 4. 内层 Kernel（ReAct / tool loop）

### 4.1 目标语义

每个 Agent Node 内：

```text
Observe(artifact/context)
  → Think/Act(choose tool)
  → Tool result
  → Observe
  → ... (bounded)
  → Final(outputs)
```

Kernel 的 plan 只能拆当前 Node，不能改变外层 Workflow。

### 4.2 当前实现

`kernel/loop.py`：

```python
Goal(node_id, objective, max_steps, max_usd)
ToolBox.register(name, fn)
Kernel.run(goal, toolbox, completer)
```

`completer(history)` 返回：

```json
{"action": "tool", "tool": "search_topic", "args": {...}}
```

或：

```json
{"action": "final", "outputs": {...}}
```

当前 Loop：

- 有工具调用；
- 有 final；
- 有 max_steps；
- 有 cancel；
- **没有** token 级 reasoning；
- **没有** LLM planner；
- **没有** tool budget/cost 累加；
- **没有** checkpoint；
- **没有** no-progress 检测。

所以更准确叫：

> **action loop / minimal ReAct-compatible loop**，不是完整 ReAct agent。

### 4.3 目标 Kernel

```text
Kernel
  context: L0 invariants / L1 artifacts / L2 working / L3 raw refs
  tools: schema + timeout + cost
  loop: think → act → observe → compact
  checkpoint per step
  budget/cancel/stagnation
  event: token.delta / tool.called / tool.result
```

Report 每个方向、Chat 每次回答都应跑一个 Kernel。

---

## 5. Report 端到端链路

### 5.1 当前链路

```text
RunShell.prepare
  → WorkflowRunner
  → source: LocalCorpus/OpenAlex → SourceArtifact
  → evidence: PaperCard/claim/quote → EvidenceArtifact
  → map: token-vector + average-link → MapArtifact
  → write: 模板章节 → ReportDraft
  → finalize: reports/sections/claims/citations
  → metrics
```

### 5.2 数据契约

#### SourceArtifact

```json
{
  "topic_id": "...",
  "query": "...",
  "papers": [{"paper_id": "...", "title": "...", "abstract": "...", "url": "..."}],
  "readiness": {"requested": 100, "retrieved": 135, "relevant": 100},
  "provenance": {"strategy": "openalex", "retrieved_at": "..."}
}
```

#### EvidenceArtifact

```json
{
  "papers": [{
    "paper_id": "...",
    "title": "...",
    "abstract": "...",
    "level": "L1|L2",
    "fulltext_available": true,
    "quote_windows": [{"text": "...", "section": "...", "page": 1}],
    "claims": [{"claim_id": "...", "text": "...", "quote": "..."}]
  }],
  "coverage": {"papers": 100, "with_claims": 84, "fulltext": 5},
  "stats": {"quote_checks": 185, "quote_ok": 185, "claims": 185}
}
```

#### MapArtifact

```json
{
  "directions": [{
    "direction_id": "D1",
    "name": "...",
    "paper_ids": ["..."],
    "claim_ids": ["..."],
    "coherence": 0.17,
    "outliers": []
  }],
  "papers": 100,
  "min_size": 6,
  "outlier_rate": 0.0,
  "count_quality": "deficit"
}
```

#### ReportDraft

```json
{
  "title": "...",
  "content_md": "...",
  "content_sha": "...",
  "sections": [{"section_id": "D1", "kind": "deep_dive", "title": "...", "body": "...", "claim_indexes": [1,2]}],
  "word_count": 2519,
  "claims": [],
  "state": "complete|degraded"
}
```

### 5.3 当前生成的报告结构

```text
At a Glance
D1..Dn Deep Dive
Comparison Matrix
Gaps & Limitations
Method & Scope
Paper Index
Claim Ledger
```

问题（见 `TODO.md`）：

- claim 计数不一致；
- paper index 只有 ID；
- 方向名泄漏作者；
- 作者列表被当 claim；
- ledger 刷覆盖率；
- 86 篇只写 6 条。

### 5.4 目标链路

```text
ReportPlan（只定结构）
  → per-direction EvidencePack
  → LLM 写 direction section
  → code gate + verifier + section score
  → append
  → global overview / comparison / gaps
  → full-report consistency check
```

---

## 6. Chat 链路

```text
ChatService.answer
  → LocalCorpus
  → token match → ranked papers
  → Kernel:
       search_topic
       verify_claim
       final
  → citations
  → ChatStore.append(session)
```

当前：

- 确定性检索；
- 无 LLM 生成；
- 可选 `composer` 注入；
- 有 session 持久化。

目标：

- 每轮走 Kernel；
- LLM grounded composer；
- token 流；
- 引用必须来自 snippets。

---

## 7. RunShell 生命周期

### 7.1 状态

```text
pending → running → succeeded
                  → failed
                  → paused → running
                  → aborted
```

### 7.2 prepare

- 生成 run_id；
- 写 `runs`；
- 保存 `request_json`。

### 7.3 run

- 写 `state=running`；
- 创建 `EventLog`；
- `WorkflowRunner`；
- 成功写 `succeeded`；
- 异常写 `failed`；
- `RunInterrupted` 写 `paused`。

### 7.4 pause/resume

- pause：把 run 置 `paused`；
- WorkflowRunner 在 Node 边界检查 state；
- resume：置 `running`，重新执行，跳过 committed Node；
- Report 的 resume 依赖 artifact 反序列化。

限制：

- 长 Node 内部不能 pause；
- 需要 Node 内 step checkpoint 才能细粒度暂停。

---

## 8. 存储

### 8.1 SQLite

```text
runs
run_nodes
run_artifacts
run_events
reports
report_sections
claims
citations
metric_points
run_spans
experiments
chat_sessions
chat_messages
```

### 8.2 Artifact Store

- 内容寻址：`sha256(payload).json`；
- DB `run_artifacts` 存 sha；
- resume 通过 sha 读 payload；
- 避免 DB 存大 JSON 重复。

### 8.3 一致性

- Node commit：artifact 先写，DB 后写；
- 报告：claims/sections/report 同事务；
- `report_id = run_id:content_sha`。

---

## 9. 事件 / API / SSE

### 9.1 事件

```text
run.started
node.started
node.finished
node.failed
section.delta
run.paused
run.finished
run.failed
```

当前 `EventLog`：

- 写 `run_events`；
- seq 从 DB `MAX(seq)+1` 生成；
- 不是单写者，高并发需改进。

### 9.2 API v2

```text
POST /api/v2/runs
GET  /api/v2/runs/{id}
GET  /api/v2/runs/{id}/report
GET  /api/v2/runs/{id}/events       SSE
POST /api/v2/runs/{id}/pause
POST /api/v2/runs/{id}/resume
POST /api/v2/runs/{id}/abort
GET  /api/v2/reports/{id}
POST /api/v2/chat
GET  /api/v2/chat/sessions/{id}
GET  /api/v2/chat/stream
GET  /api/v2/health
```

### 9.3 SSE

- `id: seq`；
- `event: type`；
- `data: JSON`；
- 支持 `Last-Event-ID` 重放；
- 终态关闭。

---

## 10. 指标

`metrics/catalog.py`：

- `search.coverage`
- `search.duplicate_rate`
- `fulltext.available_ratio`
- `card.quote_verbatim_rate`
- `claim.purity`
- `claim.citation_coverage`
- `cluster.count`
- `cluster.min_size`
- `cluster.outlier_rate`
- `report.words`
- `report.citation_coverage`
- `report.uncited_facts`
- `report.claim_coverage`
- `direction.max_share`

当前问题：

- 部分指标是结构性计数，不是质量；
- `claim.purity` 实际恒为 1；
- `uncited_facts` 硬编码 0；
- `claim_coverage` 被 ledger 刷高；
- 字数被当成质量。

目标：模块分 + 方向分 + 硬门禁 + confidence，字数只做 gate。

---

## 11. 评估

```text
evaluation/dataset.py
evaluation/evaluators.py
evaluation/runner.py
```

当前：

- dataset load + SHA 冻结；
- direction F1；
- report words/citation；
- Tuner 写 experiments。

未完成：

- 100 篇 × 3 topic gold；
- 人工 rubric；
- LLM judge；
- 真实调参闭环。

---

## 12. 当前实现状态矩阵

| 能力 | 状态 | 说明 |
|---|---|---|
| 固定 Workflow | ✅ | Report 5 节点 |
| Report 节点 Kernel 化 | ❌ | 仍是 deterministic handler |
| Chat Kernel | ✅ | minimal action loop |
| 完整 ReAct | ❌ | 无 reason/step checkpoint |
| Artifact 契约 | ✅ | JSON + sha |
| Node resume | ✅ | committed skip |
| Node 内 pause | ❌ | 仅边界 |
| CodeVerifier | ✅ | postconditions |
| AgentVerifier | ❌ | 未迁入 |
| SSE | ✅ | section/event + replay |
| LLM 写作 | ❌ | 未接 |
| LLM 审计 | ✅ | 已跑，报告 reject |
| 100 篇真实报告 | ⚠️ | 可跑，degraded |
| 真实评估集 | ❌ | 只有 20 篇 silver |
| 旧系统 | 已移出 | archive 外置 |

---

## 13. 扩展规则

新增一个 Node：

1. 在 `contracts.py` 定义 NodeSpec；
2. 定义 input/output artifact；
3. 实现 domain service；
4. 注册 handler；
5. 增加 postconditions；
6. 增加 metric gate；
7. 增加测试；
8. 更新本文件。

新增一个 Tool：

1. 在 ToolBox 注册；
2. schema；
3. timeout；
4. error code；
5. 事件；
6. 测试。

禁止：

- Node 直接互相调用；
- domain service 直接写 DB 绕过 persist；
- Workflow 运行时改拓扑；
- import 旧 `lit_agent`；
- 用 ledger/index 刷 coverage。

---

## 14. 目标架构（Phase 4）

```text
ReportPlan
  → direction job:
       EvidencePack
       → Kernel(LLM)
       → SectionArtifact
       → CodeGate + AgentVerifier + SectionScore
       → append
  → global assembly:
       overview
       comparison
       gaps
  → full consistency check
  → publish
```

核心变化：

- Report 节点真正 Kernel 化；
- 每方向独立 LLM 写作；
- 每 section 独立评分/重试；
- 全报告计数一致；
- 评分按模块/方向加权，字数只做 gate；
- AgentVerifier 接入主链路。

---

## 15. 相关文档

- `docs/TODO.md` — 当前 P0/P1 缺陷
- `docs/implementation/RESULTS-P3.6-LIVE.md` — 100 篇真实联调与审计
- `README.md` — 运行方式
