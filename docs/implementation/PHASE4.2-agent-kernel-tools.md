# Phase 4.2 · Generic Agent Kernel + Specialized Workflows

> 版本：2.1（2026-11-03）
> 类型：详细设计与迁移方案
> 状态：Kernel done；L3 gate passed；S10.0 report CLI 已跑通；API/resume 未完成；Chat 后置
> 优先级：report workflow v2 > report quality > D 盘约束 > 三库/RAG > Chat
> 依据：DSH `core/tools`、`core/agent-loop`、`compaction` 与 Phase 4.1 实现

---

## 0. 核心结论

```text
Kernel 是通用的。
Workflow 是特制的。
```

不是：

```text
Workflow 通用 + 报告 Profile
```

而是：

```text
通用 Kernel
  = 可以独立完成复杂任务
  = 不知道 report / paper / claim
  = 可以用于研究、分析、写作、代码、数据处理

特制 Workflow
  = 针对具体任务拆分阶段
  = 约束 Kernel 在每个阶段做什么
  = 验收每个阶段的中间产物
  = 报告 / Chat / 评估各自不同
```

一句话：

```text
先把发动机做好，再为不同场景做外壳。
```

---

## 1. 目标与非目标

### 1.1 目标

```text
1. 通用 Agent Kernel 可以独立完成复杂任务
2. Tool 契约标准化，Agent 能动态选择工具
3. 通用工具（context/plan/memory/test/verify）可用
4. Kernel 支持多步骤、长任务、压缩、计划、纠错、恢复
5. Workflow 是特制任务壳，负责拆分和约束
6. 报告 Workflow 在 Kernel 验收之后接入
7. Chat Workflow 后续复用同一 Kernel
```

### 1.2 非目标

```text
不做“通用 Workflow”
不把报告规则写进 Kernel
不让 DemoOrchestrator 进入生产路径
不在 Phase 4.2 完整实现 Chat
不照搬 DSH 的全部插件体系
```

---

## 2. 双层架构

```text
Interface
  API / UI / CLI
       │
Workflow Layer（特制）
  report workflow
  chat workflow
  research workflow
  evaluation workflow
       │  每个 Node 调用 Kernel
Kernel Layer（通用）
  turn / step
  context / plan / memory
  tool scheduler
  verify / repair
  checkpoint / cancel
       │
Tool Layer
  general tools + domain tools
       │
Storage
  run / node / session / artifact / report / settings
```

### 2.1 Kernel 职责

```text
给定 KernelTask：
  goal
  inputs
  toolset
  output schema
  policy
  verifier

自主完成：
  计划
  选择工具
  多步骤执行
  观察结果
  压缩上下文
  失败恢复
  self-check
  final
```

Kernel 不知道：

```text
report
paper
claim
section
citation
```

Kernel 只认识：

```text
Goal
Message
Tool
Observation
Context
Plan
Memory
Budget
Checkpoint
Artifact
Verifier
```

### 2.2 Workflow 职责

Workflow 是任务特制壳：

```text
把大任务拆成多个阶段 / AgentTask
定义每阶段目标、输入、输出、工具集、验收
控制顺序、并行、重试、暂停、人工确认
约束 Kernel 不要跑偏
```

Workflow 负责：

```text
报告：
  检索下载 → 阅读分析 → 证据 → 规划 → 写作 → 验收

Chat：
  理解问题 → 检索证据 → 回答 → 引用检查

评估：
  跑分 → 对比 → 报告
```

Workflow 不负责：

```text
LLM 循环
工具执行
上下文压缩
通用重试
```

### 2.3 Node 的定位

```text
Node 是 Workflow 的一个阶段。
Node 不是 Kernel 的领域类型。
```

```text
Workflow Node
  = goal
  + inputs
  + toolset
  + output schema
  + stage verifier
  + budget
       │
       ▼
KernelTask
  = Node 传给 Kernel 的通用请求
```

Kernel 可以在没有 Workflow 的情况下单独运行：

```python
kernel.run(
    KernelTask(
        goal="分析这个代码库并输出架构摘要",
        inputs={"root": "..."},
        toolset="general+filesystem",
        output_schema=...,
        verifier=...,
    )
)
```

这是 Phase 4.2 的第一验收目标。

---

## 3. DSH 研究结论

### 3.1 DSH Tools

DSH 把工具定义为：

```text
name + description
+ typed input schema
+ canonical output schema
+ execute(args, exec)
+ timeout / cancellation
+ parallel-safe / exclusive
+ presentation
```

调用经过固定流水线：

```text
input validation
→ pre-execute allow/deny/ask
→ guard
→ execute wrapper（timeout/retry/metrics）
→ output validation
→ post-execute
→ finalize content
→ tool/result event
```

工具失败是结构化结果，不会结束 turn。

工具可见性通过 registry + scoped restriction + agent toolset 控制，而不是多个互不相通的 Registry。

### 3.2 DSH Agent Loop

DSH 的 Agent loop 是通用内核：

```text
turn
  → step
    → claim inbox / steering
    → pre-step
    → assemble prompt + tools
    → model request
    → assistant message
    → tool scheduler
    → durable tool results
    → next step
```

关键能力：

```text
turn / step 状态机
inbox / steering
cancellation
parallel-safe / exclusive tool scheduler
structured tool errors
session / event log
checkpoint / recovery
context compaction
```

Compaction 是 `agent/pre-step` 策略，不是模型自由调用的普通工具；同时提供自动阈值和手动 `/compact`。

### 3.3 借鉴与不照搬

借鉴：

```text
Tool 是有输入/输出契约的执行体
Tool 调用有统一流水线
工具失败是结果
工具可见性与 Agent/Node 绑定
Kernel 有 turn/step 边界
工具并行/顺序调度
checkpoint / session
context compaction 是内核能力
```

不照搬：

```text
Cordis 全量插件系统
PTC run_code
完整 event sourcing
subagent / 多 Agent
browser / computer-use
```

---

## 4. 通用 Kernel 设计

### 4.1 KernelTask

```python
@dataclass(frozen=True)
class KernelTask:
    task_id: str
    goal: str
    inputs: dict[str, Any]
    toolset: str
    output_schema: dict[str, Any]
    verifier: VerifierProfile
    policy: KernelPolicy
```

`KernelPolicy`：

```python
max_steps
max_usd
max_tokens
max_tool_calls
max_repair
timeout_s
soft_context_ratio
hard_context_ratio
```

Kernel 不接收 `WorkflowDefinition`。

---

### 4.2 Kernel 循环

```text
load checkpoint
emit turn.started

for step in 1..max_steps:
    check stop / budget / timeout
    consume inbox / steering
    build context:
      goal
      plan
      memory
      compacted history
      visible tool schemas
    ask LLM
    parse action:
      tool calls
      plan update
      final
    if final:
      verify
      if accept: checkpoint + return
      if repair: inject problems; continue
    if tool:
      schedule tool calls
      append observations
      checkpoint
  return max_steps / budget / no_progress
```

### 4.3 Kernel 必须具备

```text
动态工具选择
多工具调用
并行 / 顺序调度
完整 history（不是 history[-8:]）
上下文压缩
计划
记忆
工具输出 artifact spill
结构化工具错误
self-verification
repair loop
checkpoint / resume
cancel / pause
```

### 4.4 Kernel 禁止

```text
import report
import paper / claim
判断“这是报告任务”
写死 source → evidence → report
依赖 DemoOrchestrator
```

### 4.5 当前 Kernel 的缺口

```text
_messages 只传 history[-8:]
context.compacted 只是字符截断
tool output 直接截断，不可恢复
没有 plan / memory / test
没有 repair loop
没有 toolset view
没有统一 tool pipeline
```

这些是 Phase 4.2 重点。

---

## 5. Tool 标准化

### 5.1 ToolSpec

```python
ToolSpec(
    name,
    namespace,
    title,
    description,
    version,

    input_schema,
    output_schema,

    side_effect,
    parallel_safe,
    idempotent,
    requires_approval,

    timeout_s,
    max_output_chars,
    max_retries,
    retry_on,
    cost_usd,

    capabilities,
    tags,

    handler(args, context),
    render(args, output),
)
```

### 5.2 ToolContext

```python
ToolContext(
    run_id,
    node_id,
    call_id,
    workspace,
    signal,
    budget,
    events,
    artifacts,
    settings,
)
```

### 5.3 ToolResult

```python
ToolResult(
    ok,
    output,
    content,
    error,
    artifact_refs,
    duration_ms,
    cost_usd,
    retryable,
    truncated,
)
```

### 5.4 Tool 流水线

```text
resolve visible tool
→ validate input
→ policy / guard
→ execute with timeout + cancellation
→ validate output
→ artifact spill if oversized
→ postprocess / render
→ structured result
→ tool/result event
```

错误码：

```text
E_TOOL_NOT_FOUND
E_TOOL_SCHEMA
E_TOOL_TIMEOUT
E_TOOL_CANCELLED
E_TOOL_EXECUTION
E_TOOL_OUTPUT_SCHEMA
E_TOOL_POLICY_DENIED
E_TOOL_APPROVAL_REQUIRED
```

---

## 6. 工具分层

### 6.1 一个 Registry

```text
ToolRuntime
  + ToolSpec.namespace
  + toolset
  + policy
```

不建立两个互不相通的 Registry。

### 6.2 通用工具

```text
context.inspect
context.compact
plan.create
plan.update
plan.read
plan.complete_step
memory.write
memory.search
artifact.put
artifact.get
fs.read
fs.list
test.run
verify.code
verify.audit
```

通用工具是 Kernel 的基础能力。

### 6.3 领域工具

```text
source.*
corpus.*
claims.*
report.*
chat.*
eval.*
```

领域工具由 Workflow / Tool Pack 注入，不进入 Kernel 代码。

### 6.4 Toolset

```python
GENERAL_TOOLSET = [...]
REPORT_TOOLSET = GENERAL_TOOLSET + [...]
CHAT_TOOLSET = GENERAL_TOOLSET + [...]
SOURCE_TOOLSET = GENERAL_TOOLSET + [...]
```

分类用于：

```text
权限
Prompt 体积
预算
UI 分组
审计
测试
```

不是：

```text
Agent 不能调用专用工具
```

---

## 7. Context / Plan / Memory

### 7.1 Context 压缩

```text
Kernel 自动 hard-limit 压缩
+
Agent 可调用 context.compact
```

```text
soft 0.6：Agent 可主动压缩
hard 0.85：Kernel 强制压缩
overflow：最大压缩，失败则 Node failed
```

必须保留：

```text
goal
current plan
todo
pinned artifact / evidence refs
recent messages
```

压缩结果写入 summary + artifact + event，不是简单 `truncated: true`。

### 7.2 Plan

```text
plan.create
plan.update
plan.read
plan.complete_step
```

Plan 是持久状态，每步注入摘要，不是一次性 prompt。

### 7.3 Memory

```text
memory.write
memory.search
memory.delete
```

作用域：

```text
run
node
topic
```

---

## 8. Kernel 独立验收任务

在接报告之前，Kernel 必须通过这些任务：

```text
任务 A：读取 workspace，分析代码结构，输出摘要 artifact
任务 B：检索资料，生成带引用的研究简报
任务 C：运行测试，定位失败，修复并重跑
任务 D：读取一批文件，抽取结构化数据
任务 E：多步骤长任务，中途压缩上下文并 resume
```

每个任务检查：

```text
是否自主选择工具
是否出现 plan.update
是否在需要时 context.compact
是否在失败后 repair
是否 checkpoint / resume
是否最终通过 verifier
```

这一组测试不加载 report tool。

只有通过后，才进入报告 Workflow。

---

## 9. 特制 Workflow

### 9.1 Workflow 只提供外壳

```text
WorkflowDefinition
  顺序 / 并行
  输入输出引用
  optional / retry / pause / human gate
  stage verifier
  budget
```

WorkflowRunner 是通用机制，但**具体 Workflow 是特制的**。

```text
workflow/
  core/
    definition.py
    runner.py
    state.py
  report.py
  chat.py
  research.py
```

不存在 `profiles/generic` 或“通用报告 Workflow”。

### 9.2 报告 Workflow v2（5 个核心 Node）

Phase 4.2 的 Workflow 目标只有报告：

```text
先完成 report
Chat 后置
```

当前 CLI 已有 `report-v2` 5 Node 实现；API 仍是旧 `demo100` + `DemoOrchestrator`。
下面是完整迁移目标，API 和 resume 仍未完成。

架构约束：

```text
Kernel 不 import report / paper / claim
Node 拥有领域 tools / prompt / schema / verifier
Workflow 只负责拆阶段、传产物、控制顺序和重试
领域规则不能进入 Kernel
```

#### 9.2.1 总体链路

```text
request
  → source.collect
  → evidence.extract
  → [map.classify]        可选，仅 features.classification=true
  → report.plan
  → report.write
  → report.audit_finalize
```

原则：

```text
一个 Node 一个可验收的阶段产物
Node 拥有领域约束
Kernel 只执行通用任务
每个 Agent Node 至少 3 个工具
禁止单工具 Agent Node
生产路径禁止 DemoOrchestrator
```

#### 9.2.2 Node 契约

| Node | 输入 | 工具集 | 输出 | 阶段 Verifier | 预算 |
|---|---|---|---|---|---|
| `source.collect` | `request` | `source.collect`, `corpus.stats`, `context.inspect`, `plan.update` | `SourceArtifact` | schema / unique / fulltext ratio | 6 steps / 0.20 USD |
| `evidence.extract` | `source.collect` | `evidence.extract`, `corpus.papers`, `claims.extract`, `quote.check`, `context.compact` | `EvidenceArtifact` | schema / exact quote / purity / min claims | 8 steps / 0.30 USD |
| `report.plan` | `evidence.extract`, `requirements` | `report.plan_v2`, `context.inspect`, `plan.update`, `artifact.put` | `ReportPlan` | required sections / coverage / no empty section | 6 steps / 0.20 USD |
| `report.write` | `report.plan`, `evidence.extract` | `report.write_v2`, `report.check_section`, `context.compact`, `artifact.put` | `ReportDraft` | per-section citation / word gate / grounding | 12 steps / 1.20 USD |
| `report.audit_finalize` | `report.write`, `requirements` | `report.finalize_v2`, `report.assemble`, `report.persist`, `verify.code`, `context.inspect` | `FinalReport` | assemble / citation coverage / code / audit | 8 steps / 0.30 USD |

可选：

```text
map.classify
  evidence.extract → map.classify → report.plan
  只有 features.classification=true 才插入
  不作为核心链路
```

`scorecard.build` 不进入本轮核心链路，评估后置。

#### 9.2.3 每个 Node 为什么这样设计

**source.collect**

```text
职责：获取论文、全文、去重、统计覆盖
为什么单独：检索/下载最贵且最不稳定，失败后不应重跑写作
关键验收：unique、fulltext ratio、来源可追溯
```

**evidence.extract**

```text
职责：阅读论文、抽取 exact-quote claims、过滤、去重
为什么单独：证据质量决定报告上限；可复用、可重建
关键验收：quote 原文命中、claim 不是作者/参考文献
```

**report.plan**

```text
职责：把 evidence 变成可验收的大纲
为什么单独：先验收结构，再花费写作文本；避免边写边改结构
关键验收：section 数、必需类型、evidence 覆盖
```

**report.write**

```text
职责：逐 section 写作、引用、局部重试
为什么单独：写作最不稳定；单节失败不应重跑全篇
关键验收：每个 section 有 citation、事实有 claim 支撑
```

**report.audit_finalize**

```text
职责：组装、持久化、code/audit 双验收
为什么单独：发布必须经过独立门禁，不能与写作混在一起
关键验收：citation coverage、文件存在、hash、audit
```

#### 9.2.4 产物与交换

Node 之间传引用，不传大文本：

```text
SourceArtifact
  source_path
  papers
  fulltext_ratio
  state

EvidenceArtifact
  evidence_path
  papers
  claims
  quote_checks

ReportPlan
  plan_path
  sections
  coverage

ReportDraft
  draft_path
  sections
  word_count
  citation_coverage

FinalReport
  report_path
  content_sha
  state
  papers
  claims
```

大文件放在 `D:\lit-agent-store`，SQLite 只存索引、状态、指标和路径。

#### 9.2.5 端到端报告验收

必须用真实 LLM 跑完整链路，不允许用 `DemoOrchestrator`：

```text
100 篇论文
fulltext >= 35，或显式 degraded
claims >= 100
sections >= 10
word_count 3500–8000
citation_coverage = 1.0
每个 Node 通过 stage verifier
最终 final verifier + audit 通过
report.md 和 report.json 可打开
run 状态 complete
```

#### 9.2.6 S10 实施顺序

```text
S10.0 KernelNodeAdapter 接入 WorkflowRunner
S10.1 定义 5 节点 WorkflowDefinition
S10.2 补齐 source/evidence 领域工具与 schema
S10.3 补齐 plan/write/audit 工具与 verifier
S10.4 本地 100 篇 corpus 端到端跑通
S10.5 checkpoint/resume 与失败恢复
S10.6 移除生产 DemoOrchestrator
S10.7 回归、指标、文档、提交
```

S10 不包含：

```text
Chat
Qdrant
Kuzu
```

### 9.3 Chat Workflow · deferred

Chat 不进入 Phase 4.2 交付：

```text
ConversationSession
retrieve
answer
citation verify
```

等 report workflow 稳定后，复用同一 Kernel 和同一 RetrievalPort 再做。

## 10. 迁移顺序

### 4.2.0 Baseline · done

- 84 tests 通过。
- 记录 Phase 4.1 报告链路。

### 4.2.1 Tool contracts · done

- ToolSpec / ToolContext / ToolResult
- output schema
- namespace / toolset
- policy
- structured errors

### 4.2.2 ToolRuntime · done

- registry view
- pipeline
- parallel scheduler
- artifact spill
- cancellation
- tool events

### 4.2.3 General tools · done

```text
context.inspect
context.compact
plan.*
memory.*
artifact.*
fs.*
test.run
verify.code
verify.audit
```

### 4.2.4 Generic Kernel · done

- KernelTask
- turn/step
- full history + compaction
- plan/memory
- repair loop
- checkpoint
- cancel / pause

### 4.2.5 Kernel acceptance · done

运行第 8 节的 A–E 任务。

**不通过不许写报告 Workflow。**

### 4.2.6 Kernel completeness · done

目标：先把 Kernel 做到完善可用，再碰 Workflow。

- 工具并行调度（parallel_safe / exclusive）
- 持久化 checkpoint / session / resume
- 模型 retry / backoff / token / cost
- context soft/hard compaction / overflow recovery
- 取消与 drain
- streaming（可后置但接口先定）
- 严格 output schema / failure classification

### 4.2.7 NodeKernelAdapter · done

只做一个 Node 入口，不改 Workflow：

```text
NodeSpec -> KernelTask -> AgentKernel.run -> NodeResult
```

用途：

```text
让 Kernel 通过 Node 入口被调用
验证输入输出合法
验证 checkpoint / metrics / logs
不进入 report workflow 优化
```

### 4.2.8 Observability · done

- kernel event taxonomy
- metrics：success/steps/tokens/cost/latency/tool errors
- error taxonomy：E_KERNEL_* / E_MODEL_* / E_TOOL_*
- 日志脱敏
- benchmark 结果落库

### 4.2.9 Kernel benchmark + performance · done

必须完成真实 LLM 多任务基准：

```text
30+ tasks
real model
no report tools
```

门禁：

```text
schema pass >= 99%
simple task success >= 90%
complex task success >= 70%
no uncaught kernel exception
resume works
context compaction observable
```

未通过：

```text
禁止修改 Workflow
```

已完成 30 个真实简单任务和 14 个复杂任务；L3 gate passed，详见 `RESULTS-P4.2-L3-GATE.md`。

### 4.2.10 Workflow core + report shell · in progress

只有 Kernel 门禁通过后才开始。当前 Kernel 门禁已通过。

- CLI 已接入 `KernelNodeAdapter`
- 五节点 report workflow 已跑通 100 篇
- 每 Node >= 3 tools
- API 仍走旧 Kernel + DemoOrchestrator
- Node checkpoint / resume 未接
- 真实 100 篇 CLI 报告已通过

S10.0 记录：`RESULTS-P4.2-S10.0.md`。

### 4.2.11 Report optimization

- 100 篇 fulltext
- 分节写作与局部重试
- citation / evidence / audit
- 报告质量门禁

### 4.2.12 Chat · deferred

Report workflow 稳定后再做：

- ConversationSession
- chat workflow
- 同一 Kernel
- 真实 LLM
- streaming 可后置

### 4.2.13 Cleanup

- 删除 `demo.orchestrator`
- 删除单工具 demo
- docs / tests / commit

---

## 10.1 Kernel → Workflow 门禁

```text
Kernel feature checklist 完成
NodeKernelAdapter smoke 通过
30+ 真实 LLM benchmark 完成
指标达标
日志/错误系统完整
```

当前状态：passed。

详见 [`docs/KERNEL-MATURITY.md`](../KERNEL-MATURITY.md) 与
[`RESULTS-P4.2-L3-GATE.md`](RESULTS-P4.2-L3-GATE.md)。

## 10.2 Report Workflow 门禁

```text
5 个 Node 全部通过 stage verifier
100 篇真实 LLM 端到端
report.md / report.json 可打开
citation_coverage = 1
run state complete
不依赖 DemoOrchestrator
Node checkpoint / resume 可用
```

未通过：

```text
不允许宣称 report workflow 完成
不允许进入 Chat
```

---

## 11. 测试矩阵

```text
tool input schema
tool output schema
tool timeout / cancel / retry
tool policy
parallel-safe vs exclusive
artifact spill
context.compact
plan lifecycle
memory search
kernel repair
kernel max_steps / budget
checkpoint resume
Kernel task A–E
workflow report
workflow report resume
workflow report 100-paper e2e
workflow chat deferred
100-paper fulltext
no report imports in kernel
no DemoOrchestrator in src
each agent Node >= 3 tools
```

新增守卫：

```text
test_no_single_tool_agent_node
test_no_demo_orchestrator_in_src
test_kernel_has_no_report_imports
test_generic_agent_without_report_tools
```

---

## 12. 文件布局

```text
src/lit_agent_v2/
  contracts/
    kernel.py
    tool.py
    node.py
    workflow.py
  kernel/
    agent/
      loop.py
      context.py
      scheduler.py
      policy.py
      checkpoint.py
    llm.py
  tools/
    runtime.py
    schema.py
    sets.py
    general/
      context.py
      plan.py
      memory.py
      artifact.py
      test.py
      verify.py
      fs.py
    domain/
      source.py
      corpus.py
      claims.py
      report.py
      chat.py
  workflow/
    core/
      definition.py
      runner.py
      state.py
    report.py
    chat.py
    research.py
  storage/
    db.py
    session_store.py
    artifacts.py
    report_store.py
  settings/
    config.py
    store.py
```

---

## 13. 关键决策

```text
1. Kernel 通用，Workflow 特制
2. Kernel 不知道领域
3. Workflow 负责拆分、约束、阶段验收
4. Tool 有输入/输出契约和统一流水线
5. 工具分类是 namespace/toolset/policy，不是多个 Registry
6. Context compaction 是 Kernel 能力 + 可选内部 Tool
7. Plan / Memory 是 Kernel 能力
8. Repair 是 Kernel 能力
9. Agent Node 至少 3 个工具
10. 报告优化只允许改 report Workflow / tools / verifier
11. 先通过 Kernel A–E 验收，再做报告
12. Chat 后续复用同一 Kernel
```

---

## 14. 验收

```text
84+ tests 全绿
ruff clean
npm run build 通过
Kernel A–E 任务通过
每个 agent Node >= 3 工具
至少一次 context.compact
至少一次 plan.update
至少一次 verify.repair
生产路径无 DemoOrchestrator
kernel 无 report import
100 papers
fulltext >= 30%
report complete
Chat smoke 走同一 Kernel
```

---

## 15. Commit 序列

```text
feat(T-01): standardize tool contracts and tool runtime
feat(K-02): add generic kernel task loop
feat(K-03): add context, plan, memory and repair
feat(T-04): add general tools
test(K-05): add kernel-only acceptance tasks
feat(W-06): add workflow core and report shell
feat(R-07): migrate report workflow to multi-tool nodes
feat(C-08): move chat onto the shared kernel
docs(4.2): record acceptance and cleanup
```

---

## 16. DSH 参考

```text
packages/core/tools/README.md
packages/core/tools/src/index.ts
packages/core/tools/src/types.ts
packages/core/tools/src/schema.ts
packages/core/tools/src/json-schema.ts
packages/core/agent-loop/README.md
packages/core/agent-loop/src/agent.ts
packages/core/agent-loop/src/tool-calls.ts
packages/compaction/compaction-basic/README.md
packages/compaction/compaction/README.md
```

借鉴：

```text
typed tool + output contract
tool execution pipeline
parallel-safe / exclusive scheduler
turn / step loop
inbox / steering
structured tool errors
session / checkpoint
automatic + manual context compaction
```

不照搬：

```text
Cordis 插件系统
PTC run_code
完整 event sourcing
subagent / 多 Agent
browser / computer-use
```
