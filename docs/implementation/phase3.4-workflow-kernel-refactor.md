# Phase 3.4 · Workflow + Kernel 重构（固定 Workflow，共享 Agent 内核）

> **版本**：1.2.0（2026-10-30，S1–S6 已落地）
> **类型**：架构重构（大规模替换，不是局部优化）
> **前置**：Phase 3.3 已收尾（613 pytest / 18 e2e）
> **目标**：把 Report/Chat 从“两套流程 + 零散函数”重构为 **固定 Workflow + 共享 Kernel + 独立 Verifier**
> **非目标**：本阶段不做指标/评估体系；相关待办见 **docs/OPEN-ISSUES.md**（评价体系待完成）。
> **当前状态**：S1–S3 已落地（Kernel/Workflow 类型、工具注册、有界 loop）；S4+ 待做。

---

## 0. 术语（本阶段冻结）

| 术语 | 定义 |
|---|---|
| **Workflow** | 最外层、预先定义、版本化的任务流程；**没有运行时 plan** |
| **Node** | Workflow 中的一个任务单元；声明输入/输出/工具/预算/验收 |
| **Kernel** | DSH 式 Agent 运行时；被 Node 调用，可执行工具循环 |
| **Kernel plan** | Kernel 内部的规划工具，只拆当前 Node，不能改 Workflow |
| **Artifact** | Node 的输出物；只传引用/摘要，不传完整对话 |
| **Verifier** | Node 结束后的验收：确定性代码 + 独立 Agent |
| **Producer** | Node 内负责生成内容的 Agent |
| **Run** | 一次 Workflow 执行；可暂停、恢复、审计 |

**禁止**：

- 外层 Workflow 内做动态 plan；
- Kernel 修改 Workflow 节点；
- 把完整对话作为 Node 间接口；
- Verifier 与被验 Producer 共用同一上下文/推理。

---

## 1. 目标架构

```text
┌──────────────────────────────────────────────────────────┐
│ Workflow（固定，版本化）                                  │
│  Node A → Node B → Node C → …                            │
│  每个 Node：input/output/tools/budget/postconditions      │
└───────────────────────────┬──────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────┐
│ Node Executor                                            │
│  1. 读取 input artifact                                  │
│  2. deterministic → tool；agent → Kernel                 │
│  3. 产生 output artifact                                 │
│  4. Code Gate → Independent Verifier                     │
│  5. accept → checkpoint → next Node                      │
└───────────────────────────┬──────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────┐
│ Kernel（共享，DSH 式）                                    │
│  agent loop / tools / context / event / stream /          │
│  checkpoint / budget / cancel / local plan                │
└───────────────────────────┬──────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────┐
│ Domain Tools / Artifact Store / Run State                │
└──────────────────────────────────────────────────────────┘
```

### 1.1 与 DSH 的对应

| DSH | 本架构 |
|---|---|
| Agent loop | Kernel |
| Tool registry / execute | Kernel Tools |
| Session log / streaming | Run / Node / Step 事件 |
| Context compaction | 分层记忆 + Handoff |
| Checkpoint / resume | Node/Step checkpoint |
| Subagent | Node 内的 Producer Agent |
| Orchestrator | Workflow |
| Reviewer | Independent Verifier |

**差异**：Workflow 比 DSH 厚；领域工具更强；Report 是长 Workflow，Chat 是短 Workflow。

---

## 2. Workflow

### 2.1 固定节点

```text
ReportWorkflow:
  source → evidence → map → write → finalize

ChatWorkflow:
  answer → finalize
```

- 当前 **不由 AI 自动生成** Workflow；
- Workflow 是配置/代码，需版本化；
- 节点顺序/依赖固定；不允许运行时改图。

### 2.2 Node 契约

```python
@dataclass(frozen=True)
class NodeSpec:
    id: str
    kind: Literal["deterministic", "agent"]
    goal: str
    input_keys: tuple[str, ...]
    output_key: str
    allowed_tools: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    budget_usd: float = 0.0
    timeout_s: float = 300.0
```

- `deterministic`：不调用 LLM，只执行工具/函数；
- `agent`：调用 Kernel，Kernel 内部可选 plan；
- 节点只写 `output_key` 对应 artifact；
- 节点失败不影响已完成 artifact。

### 2.3 Node 生命周期

```text
load_input
  → execute (deterministic | kernel)
  → artifact
  → code_gate
  → verifier_agent
  → accept / repair / fail
  → checkpoint
```

- `repair`：节点内重试/修补，次数有上限；
- `fail`：节点失败，Workflow 停止或人工介入；
- **不允许** `replan workflow`。

---

## 3. Kernel

### 3.1 组成

```text
Kernel
├─ Agent loop（有界 step / budget / timeout）
├─ Tool registry（领域工具 + plan 工具）
├─ Context manager（L0–L3 分层记忆）
├─ Event/stream emitter
├─ Checkpoint / resume
├─ Cancellation
└─ Local plan
```

### 3.2 plan 的边界

- plan 是 Kernel 的工具；
- 输入：当前 Node goal + 已加载 context；
- 输出：当前 Node 的局部步骤；
- 不能新增/删除 Workflow Node；
- 不能修改 Node 输入/输出/验收；
- 无法完成 → `escalate`，由外层决定重试/失败/人工。

### 3.3 Kernel 工具

| 工具 | 作用 |
|---|---|
| `search_topic` | 检索论文/片段 |
| `fetch_paper` | 获取全文/元数据 |
| `build_card` | 论文卡片 |
| `extract_claims` | claim + quote |
| `cluster_directions` | 方向聚类 |
| `draft_section` | section 草稿 |
| `validate_citations` | 引用/quote 校验 |
| `compress_context` | 上下文压缩 |
| `plan_steps` | 当前 Node 局部计划 |

工具必须有：

- JSON schema；
- side effect 标记；
- 超时；
- 输出上限；
- 调用事件。

### 3.4 上下文分层

| 层 | 内容 | 跨 Node |
|---|---|---|
| L0 | topic、scope、预算、用户约束 | 永久 |
| L1 | artifact 摘要、claim ledger、方向 | 保留引用 |
| L2 | 当前 Node 工具结果/推理 | 仅当前 Node |
| L3 | 原始 LLM/工具输出 | 只存 artifact |

Node 切换：

```text
保留 L0 + L1
压缩 L2 → handoff
丢弃 L3（保留引用）
```

### 3.5 事件与恢复

事件：

```text
node.started / node.finished
step.started / step.finished
tool.called / tool.result
token.delta / artifact.updated
checkpoint.saved
verifier.verdict
run.paused / run.resumed / run.failed
```

- 每 Node/Step 后 checkpoint；
- 崩溃/用户停止后从最后 checkpoint 恢复；
- 不重复调用已完成工具/LLM（按 cache + step 状态）。

---

## 4. Verifier

### 4.1 两层验收

1. **Code Gate**（先）
   - schema；
   - 输入/输出完整性；
   - citation/quote；
   - artifact 引用；
   - 预算/超时。

2. **Independent Verifier Agent**（后）
   - 独立上下文；
   - 只看 artifact + NodeContract + 证据；
   - 不看 Producer 的推理；
   - 输出：

```json
{"verdict":"accept|repair|fail",
 "reasons":[],
 "failed_checks":[]}
```

- `repair` 次数上限；
- `fail` 不进入下一 Node；
- 不允许修改 Workflow。

### 4.2 Producer / Verifier

- 一个 Node 通常 1 个 Producer Agent；
- 每个 Node 结束 1 个 Verifier Agent（可复用同一 Kernel，不同 Goal/上下文）；
- 两者模型可相同，但上下文/指令必须隔离。

---

## 5. Report Workflow

```text
source
  goal: 确定 query/venue，获取论文
  tools: source.search / source.preview
  output: papers artifact

evidence
  goal: 解析、卡片、claim
  tools: fetch/parse/build_card/extract_claims
  output: evidence artifact

map
  goal: 聚类、方向、对比
  tools: cluster_directions / compare
  output: directions artifact

write
  goal: outline + sections + critique + repair
  tools: draft_section / validate_citations / compress
  output: report draft

finalize
  goal: 最终门禁 + 报告落库
  tools: validate / commit
  output: report artifact
```

- 每 Node 独立验收；
- Node 间传 artifact + handoff；
- 长任务可数小时，流式进度；
- Kernel plan 只在 Node 内拆分步骤。

---

## 6. Chat Workflow

```text
answer
  goal: 基于 topic 证据回答/拒答
  tools: search_topic / verify_claim / compose_answer
  output: chat reply artifact

finalize
  goal: 引用/拒答校验
  output: stored message
```

- 通常 1 个 agent Node；
- 低延迟、单轮；
- 不聚类、不写 section；
- 与 Report 共用 Kernel、工具、引用校验、事件、缓存。

---

## 7. 代码目录（目标）

```text
src/lit_agent/
├─ kernel/
│  ├─ runtime.py       # Agent loop / budget / cancel
│  ├─ tools.py         # ToolRegistry + domain tools
│  ├─ context.py       # L0–L3 + compression
│  ├─ events.py        # node/step/tool streams
│  ├─ checkpoint.py    # resume
│  ├─ plan.py          # local plan tool
│  └─ types.py
├─ workflow/
│  ├─ spec.py          # WorkflowSpec / NodeSpec
│  ├─ runner.py        # node lifecycle + checkpoint
│  ├─ artifacts.py
│  ├─ verifier.py      # code gate + agent verifier
│  ├─ report.py
│  └─ chat.py
├─ report/             # domain implementation（kernel tools 调用）
├─ agents/             # 逐步迁移/删除旧入口
└─ runtime/            # legacy graph runner（过渡期兼容）
```

**迁移原则**：

1. 先建 `kernel/` + `workflow/` 新路径；
2. 把现有 report/chat 函数包装成 tools；
3. Chat 先迁（短 Workflow）；
4. Report 后迁（长 Workflow）；
5. 旧 `graph_runner` 保留为兼容层，测试通过后删除；
6. 不一次性删除旧代码，避免不可回滚。

---

## 8. 实施步骤

| 步 | 内容 | 验收 |
|---|---|---|
| S1 ✅ | 新建 `kernel/types.py`、`workflow/spec.py` | `KernelGoal/KernelResult/NodeSpec/WorkflowSpec` 可序列化；`validate_workflow` |
| S2 ✅ | Kernel tools 注册 | `KernelTools.from_cards`：search/rewrite/verify/extract/compress；tool 事件 |
| S3 ✅ | Kernel runtime | 有界 loop / budget / timeout / cancel / no_progress；8 例单测 |
| S4 ✅ | Context 分层 + handoff/compress | `start_node/finish_node` 保留 L0/L1；L2 清空；`compress` |
| S5 ✅ | Checkpoint/resume | `KernelCheckpoint` + `CheckpointStore`；resume 复用 trace/context |
| S6 ✅ | WorkflowRunner + ArtifactStore | 固定顺序、输入/输出 artifact、checkpoint、CodeVerifier |
| S7 | Code Gate + Verifier protocol | 失败可 repair/fail |
| S8 | ChatWorkflow 迁移 | Chat API 走新路径 |
| S9 | ReportWorkflow 迁移 | report API 走新路径 |
| S10 | 事件/stream 接入 UI | 节点/步骤可见 |
| S11 | 旧 graph 兼容/删除 | 全量回归 |
| S12 | 文档/收尾 | H1–H12 |

---

## 9. 验收

| # | 判据 |
|---|---|
| H1 | Workflow 固定，无运行时 plan |
| H2 | 每个 Node 有 input/output/schema |
| H3 | deterministic Node 不调用 LLM |
| H4 | agent Node 只通过 Kernel 执行 |
| H5 | Kernel plan 不能改 Workflow |
| H6 | Node 输出先过 Code Gate，再过 Verifier |
| H7 | Verifier 上下文与 Producer 隔离 |
| H8 | Node 间只传 artifact/handoff |
| H9 | 每 Node 有 checkpoint |
| H10 | 中断后可 resume，不重复已完成 Node |
| H11 | Report/Chat 共用 Kernel/Tools/引用校验 |
| H12 | 旧 API 兼容，pytest/e2e 全绿 |

---

## 10. 评价体系（延后）

本阶段**不实现**指标/评估体系。  
已迁移到：

- `docs/OPEN-ISSUES.md`（评价体系待完成）
- `docs/OPEN-ISSUES.md`

Phase 3.4 只保证：

- 事件/step 可观测；
- Node/Agent/Tool 边界清晰；
- 后续指标可以挂到统一事件上。

---

## 11. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 大重构破坏现有功能 | 新旧路径并行；旧 graph 保留 |
| Node 粒度太细 | 4–6 个粗粒度 Node |
| 上下文断裂 | 分层 memory + handoff |
| Verifier 误判 | Code Gate 优先；独立上下文 |
| 长任务卡住 | 心跳/停滞检测/取消 |
| 迁移不可回滚 | 每个 Node 独立迁移；feature flag |

---

## 12. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| 1.2.0 | 2026-10-30 | S4–S6 落地：分层 context、kernel checkpoint、workflow runner/artifact/verifier；625 pytest |
| 1.1.0 | 2026-10-30 | S1–S3 落地：Kernel/Workflow 类型、工具注册、有界 loop；621 pytest |
| 1.0.0 | 2026-10-30 | 新架构：固定 Workflow + 共享 Kernel + Producer/Verifier；评价体系移至 3.5 |
