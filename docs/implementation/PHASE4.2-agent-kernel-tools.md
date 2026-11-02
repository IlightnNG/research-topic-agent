# Phase 4.2 · Agent Kernel, Tool Standardization and Generic Workflow

> 版本：1.0（2026-11-02）
> 类型：详细设计与迁移方案
> 状态：proposed；Phase 4.1 已 complete
> 范围：Kernel、Tools、Workflow、Context/Plan/Memory、Verification、Chat
> 依据：DSH 的 `core/tools`、`core/agent-loop`、`compaction` 设计与当前 Phase 4.1 实现

---

## 1. 为什么需要 Phase 4.2

Phase 4.1 证明了：

```text
Node chain + Kernel + ToolRegistry + Verifier
```

可以跑通 100 篇全链路，但它仍然是**报告流水线**，不是通用 Agent 内核。

当前问题：

```text
1. demo 每个 Node 只允许一个工具
2. 控制流由 DemoOrchestrator 写死
3. 没有 plan / memory / test / context 通用工具
4. Kernel 只保留最近 8 条 history
5. context.compacted 是自动截断，不是可审计的压缩
6. Verifier 主要是 schema，缺少 test / audit / repair 循环
7. Workflow 和 report 领域强耦合
8. Chat 还不能复用同一 Kernel
9. 配置散落在 PowerShell 环境变量
```

Phase 4.2 的目标：

```text
把“报告流水线”升级为“通用 Agent 平台”
重点：Tool 标准化 + Kernel 循环
其次：Workflow 通用化
最后：Chat 复用同一内核
```

不是重写一个 DSH。只借用 DSH 的**边界和契约**，保持 Python 代码规模可控。

---

## 2. DSH 设计研究结论

### 2.1 Tool 的职责边界

DSH 的 `packages/core/tools` 把 Tool 定义为：

```text
name + description
+ typed parameter schema
+ canonical output schema
+ execute(args, exec)
+ timeout / cancellation
+ parallel-safe or exclusive
+ presentation metadata
```

关键点：

```text
Tool 是一个“能力声明 + 执行体”
不是一段随意函数
```

工具结果不是任意对象，而是：

```text
canonical JSON value
→ output schema validation
→ renderer 转为 model-facing content
→ presentation metadata 给 UI
```

工具调用经过固定流水线：

```text
参数校验
→ tools/pre-execute（allow / deny / ask）
→ guard
→ tools/execute（timeout / retry / metrics）
→ tools/post-execute（inspect / replace / block / context）
→ finalizeContent
→ tools/result（只观察）
```

工具失败不会结束 Agent turn：

```text
unknown tool
schema error
tool exception
timeout
abort
```

都变成结构化结果，Agent 可以在下一步修正。

DSH 还有：

```text
per-agent tool restriction
scoped registration
native schema 或 PTC SDK 两种 presentation
```

这证明：

```text
工具分类/裁剪是“可见性/权限”问题
不是“要让 Agent 才能调用”的问题
```

### 2.2 DSH Agent Loop 的职责边界

DSH 的 `packages/core/agent-loop` 不是“一个大 ReAct 函数”。

它拆成：

```text
Agent driver
  turn / step 状态机
  inbox / steering
  cancellation
  session event log
  request assembly
  tool scheduler
  recovery
```

一个 step：

```text
claim inbox
→ agent/pre-step
→ render prompt + visible tool schemas
→ model request
→ stream assistant message
→ parse tool calls
→ execute tool calls
→ durable tool results
→ next step
```

工具调度：

```text
parallel-safe calls 可以并发
exclusive calls 是顺序 barrier
结果按 model order 提交
abort 后未开始的调用写 synthetic error result
```

持久化：

```text
每个 turn / step / tool call / tool result
都进入 session log
compaction / resume / replay 都从 log 派生
```

DSH 的 context compaction 是：

```text
agent/pre-step 插件
不是模型直接调用的普通 Tool
```

它提供：

```text
automatic threshold compaction
context-overflow recovery
manual /compact command
tool-result pruner
```

模型不能任意删除上下文；压缩由内核执行，并记录 `compaction/*` 事件。

### 2.3 DSH 对 Phase 4.2 的启发

必须借鉴：

```text
1. Tool 是有输出契约的执行体
2. Tool 调用有统一流水线
3. 工具失败是结果，不是进程异常
4. Tool 可见性和 Node/Agent 绑定
5. Kernel 有 turn/step 边界
6. 工具调用按 parallel-safe/exclusive 调度
7. 每个 step 有 checkpoint/journal
8. context compaction 是内核策略
9. 允许 Agent 主动选择语义压缩，但 hard limit 必须自动兜底
```

不照搬：

```text
Cordis plugin/waterfall 全量机制
PTC run_code
完整 session event sourcing
多 Agent/subagent
浏览器/沙箱插件体系
```

这些可以后置。

---

## 3. 目标架构

```text
Workflow
  ordered Node chain
  generic; no report-specific imports

Node
  goal
  toolset
  inputs
  output schema
  kernel policy
  verifier
  budget

AgentKernel
  turn / step
  inbox / steering
  context assembly
  plan / memory / context tools
  tool scheduler
  checkpoint / journal
  stop / pause / cancel

ToolRuntime
  registry
  typed specs
  output schema
  guards / policy
  parallel scheduler
  structured errors
  artifact spill

Verifier
  code checks
  audit
  test execution
  repair loop

Storage
  run / node / event
  session
  artifact
  report
  settings
```

关键原则：

```text
Kernel 不知道 report、paper、claim
Kernel 只知道 Node、Tool、Message、Budget、Checkpoint
Workflow 只是 Node 组合
Report/Chat 都是 Workflow 的消费者
```

---

## 4. Tool 标准化

### 4.1 ToolSpec 目标字段

当前：

```python
ToolSpec(
    name,
    description,
    input_schema,
    output_schema,
    side_effect,
    idempotent,
    timeout_s,
    cost_usd,
    max_retries,
    retry_on,
    handler,
)
```

目标扩展：

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    namespace: str
    title: str
    description: str
    version: str

    input_schema: dict
    output_schema: dict

    side_effect: bool
    parallel_safe: bool
    idempotent: bool
    requires_approval: bool

    timeout_s: float
    max_output_chars: int
    max_retries: int
    retry_on: tuple[str, ...]
    cost_usd: float

    capabilities: tuple[str, ...]
    tags: tuple[str, ...]

    handler: Callable[[dict, ToolContext], dict]
    render: Callable[[dict, dict], str] | None
```

`namespace` 用于：

```text
source.*
evidence.*
report.*
context.*
plan.*
memory.*
fs.*
test.*
verify.*
chat.*
```

`capabilities` 用于权限：

```text
read
write
network
shell
llm
filesystem
```

`parallel_safe` 不能只由 `side_effect` 推导：

```text
读文件是 read，但可能和写文件冲突
http GET 通常 parallel_safe
llm.generate 不应无限并发
```

### 4.2 ToolContext

工具执行时必须拿到：

```python
@dataclass
class ToolContext:
    run_id: str
    node_id: str
    call_id: str

    workspace: Path
    signal: Callable[[], bool]

    budget: BudgetView
    events: EventPort
    artifacts: ArtifactPort
    settings: SettingsView
```

工具不再只能接收 `args`。

这样可以实现：

```text
取消
输出落盘
预算扣减
事件记录
工作目录
权限检查
```

### 4.3 ToolResult

目标：

```python
@dataclass
class ToolResult:
    ok: bool
    output: dict
    content: list[ContentBlock]  # model-facing preview
    error: ToolError | None

    artifact_refs: list[str]
    duration_ms: int
    cost_usd: float

    retryable: bool
    truncated: bool
    metadata: dict
```

错误统一为：

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

普通工具失败必须返回 `ToolResult`，不能抛到 Kernel 外层。

### 4.4 Tool 执行流水线

```text
1. resolve tool by scoped view
2. validate input schema
3. pre-execute policy
   - allow / deny / ask
4. execute with timeout + cancellation
5. validate output schema
6. if too large: write artifact and return preview
7. post-execute transform
8. structured error normalization
9. emit tool/result event
```

统一事件：

```text
tool/called
tool/result
tool/denied
tool/truncated
tool/artifact
```

### 4.5 工具可见性：分类，但不割裂

不要建立两个互不相干的 Registry。

建议：

```text
一个 ToolRuntime
+ ToolSpec.namespace / tags
+ Toolset
+ Policy
```

Toolset 示例：

```python
GENERAL_TOOLSET = [
    "context.inspect",
    "context.compact",
    "plan.create",
    "plan.update",
    "plan.read",
    "memory.write",
    "memory.search",
    "artifact.get",
    "test.run",
    "verify.code",
]

REPORT_TOOLSET = GENERAL_TOOLSET + [
    "report.plan",
    "report.write_section",
    "report.check_section",
    "report.assemble",
    "report.persist",
]

SOURCE_TOOLSET = GENERAL_TOOLSET + [
    "source.search",
    "source.fetch_pdf",
    "source.fetch_html",
    "fulltext.extract",
    "corpus.store",
    "corpus.dedupe",
]
```

Node 看到的是 toolset 解析后的**可见 schema 集**，不是整个 Registry。

分类的作用：

```text
设置页面分组
权限/审批
预算
Prompt 体积
测试
审计
```

不是：

```text
“专用工具 Agent 不能调用”
```

---

## 5. Context / Plan / Memory

### 5.1 Context 压缩

采用混合策略：

```text
Kernel 自动 hard-limit 压缩
+
Agent 可调用 context.compact
```

工具：

```text
context.inspect
  返回 token 估算、消息数、可压缩区域、pinned refs

context.compact
  strategy: summarize | drop_tool_outputs | keep_recent | custom
  keep_refs: [artifact ids, claim ids, plan ids]
  target_ratio
```

Kernel 规则：

```text
soft limit 0.6：Agent 可主动压缩
hard limit 0.85：Kernel 必须自动压缩
overflow：强制最大压缩，再失败则 Node failed
```

必须保留：

```text
system goal
current plan
current todo
pinned evidence/artifact refs
recent N messages
```

压缩结果：

```text
summary message
+ compaction event
+ artifact 保存被压缩内容
```

不是简单把旧 tool output 替换成 `truncated: true`。

### 5.2 Plan

Tool：

```text
plan.create(goal, constraints) -> plan_id
plan.update(plan_id, steps)
plan.read(plan_id)
plan.complete_step(plan_id, step_id, evidence_ref)
```

Plan 是 Node 的持久状态，不是 prompt 里的一段自由文本。

Kernel 每步把当前 plan 摘要注入上下文。

### 5.3 Memory

```text
memory.write(key, value, scope=run|node|topic)
memory.search(query, scope, limit)
memory.delete(key)
```

Memory 用于：

```text
已确认证据
失败尝试
用户约束
长期偏好
```

不能把 memory 当历史消息；它必须可检索、可引用、可清理。

---

## 6. Kernel 循环

### 6.1 目标循环

```text
run(node, context):
  load checkpoint
  emit turn.started

  for step in 1..max_steps:
    check stop/budget/timeout
    consume inbox / steering
    build context:
      system prompt
      node goal
      current plan
      relevant memory
      compacted history
      visible tools
    ask LLM
    parse action:
      final
      tool calls
    if final:
      verify
      if accept: checkpoint + return
      if repair: continue with feedback
    else:
      validate tool calls
      schedule parallel/exclusive
      append tool results
      checkpoint
  return reason=max_steps
```

### 6.2 当前 Kernel 需要修正的点

```text
_messages 只传 history[-8:]
  → 丢失上下文，必须使用完整/压缩后 history

context.compacted 只统计字符
  → 需要 token/摘要/pin/artifact

invalid action 2 次直接失败
  → 结构化错误反馈 + 可修复次数

tool output 超过 max_tool_chars 直接截断
  → 写 artifact，返回 preview + ref

没有 session/turn 日志
  → journal 和 run_events 足够，但需要统一

没有 toolset view
  → Node 只能看到 tools tuple，无法策略化

没有 plan/memory/test
  → Agent 不能做计划、记忆、自测

没有 repair loop
  → Verifier 失败直接 Node failed
```

### 6.3 Action 协议

短期保留当前 JSON：

```json
{"action": "tool", "calls": [{"id": "call_1", "name": "source.search", "args": {}}]}
{"action": "final", "outputs": {}}
{"action": "plan", "steps": []}
{"action": "verify", "checks": []}
```

Phase 4.2 增加：

```json
{"action": "repair", "feedback": "..."}
```

不建议引入 DSL 或 PTC；先用结构化 JSON。

### 6.4 Repair loop

Node 结束不是“LLM 说 final 就结束”。

```text
final
→ code verifier
→ audit verifier
→ optional test.run
→ accept / repair
```

如果 repair：

```text
把 verifier problems 作为 next-step system message
允许最多 N 次 repair
预算和步数计入 Node
超过 N 次才 failed
```

这比当前 `WorkflowRunner` 直接 `NodeFailed` 更合理。

### 6.5 Pause / cancel / checkpoint

保留当前 `should_stop`，但统一：

```text
pause request
→ Kernel step boundary
→ checkpoint
→ WorkflowInterrupted
→ resume from checkpoint
```

每个 tool 调用后和每个 step 后写 checkpoint。

---

## 7. Workflow 通用化

### 7.1 NodeSpec 调整

```python
NodeSpec(
    id,
    goal,
    mode="agent",              # agent | deterministic | human
    toolset="research",        # 解析为可见工具
    tools=(),                  # 额外显式限制
    inputs=(),
    output_schema=...,
    verifier=...,
    max_steps=...,
    max_usd=...,
    max_tokens=...,
    max_repair=2,
    optional=False,
    enabled=True,
)
```

兼容现字段，不一次性破坏。

### 7.2 Workflow 不依赖报告

目标目录：

```text
workflow/
  node/
    definition.py       # WorkflowDefinition / NodeSpec
    runner.py           # generic runner
    state.py
  definitions/
    research.py         # source/evidence/report/finalize
    chat.py             # chat workflow (Phase 4.2 后)
    evaluation.py
```

`workflow/definitions/*` 可以 import 领域 Tool 名称，但 Kernel/runner 不 import report。

### 7.3 Driver 抽象

```text
AgentDriver
  LLMDriver        # production
  ScriptedDriver   # test/demo only
```

当前 `DemoOrchestrator` 应降级为：

```text
tests/fixtures/scripted_driver.py
```

生产 full chain 必须用 `LLMDriver`，不能把写死控制流伪装成 Agent。

### 7.4 报告 Workflow 目标

```text
source.collect
  tools: source.search, source.fetch_pdf, fulltext.extract,
         corpus.store, corpus.dedupe, context.*, plan.*
  output: SourceArtifact

evidence.extract
  tools: corpus.read, claims.extract, quote.check,
         claims.dedupe, evidence.stats, context.*, plan.*
  output: EvidenceArtifact

report.generate
  tools: report.plan, report.write_section, report.check_section,
         report.assemble, citation.check, context.*, plan.*
  output: ReportDraft

finalize
  tools: report.persist, artifact.put, verify.code
  output: FinalReport
```

每个 Node 至少 3 个可用工具，且包含 `context.*` / `plan.*` 之一。

---

## 8. Chat 复用同一 Kernel

Phase 4.2 不实现 Chat，但必须预留：

```text
ConversationSession
  messages
  summary
  topic_id

chat workflow
  retrieve
  answer
  verify
```

Chat 的 Node 使用：

```text
source.search / corpus.read
memory.search
chat.answer
verify.citation
```

禁止 Chat 再依赖独立的旧 `domains.chat.answer` 逻辑。

---

## 9. Settings

集中配置，避免 PowerShell 散落：

```text
.env
  secrets only

config/settings.toml
  non-secret defaults

DB settings table
  runtime settings

run.request_json
  per-run snapshot
```

优先级：

```text
run > DB settings > settings.toml > .env > code default
```

设置页面后再提供：

```text
GET /api/v2/settings
PATCH /api/v2/settings
GET /api/v2/settings/schema
```

首批设置：

```text
model
max_steps
max_usd
max_tokens
max_repair
toolset defaults
fulltext target
report language
```

---

## 10. 迁移步骤

### 4.2.0 Baseline

- 冻结 Phase 4.1 测试：84 passed。
- 记录当前 demo 指标。
- 保存 report workflow 的 trace。

### 4.2.1 Tool contracts

- 扩展 `ToolSpec` / `ToolContext` / `ToolResult`。
- 加 output schema 校验。
- 加 `ToolRegistry.view(toolset, policy)`。
- 保留旧字段兼容。

### 4.2.2 General tools

新增：

```text
context.inspect
context.compact
plan.create
plan.update
plan.read
memory.write
memory.search
test.run
verify.code
artifact.put/get
```

先实现最小版本，不做复杂 UI。

### 4.2.3 Tool pipeline

- pre-execute guard
- timeout/cancel
- output validation
- artifact spill
- structured error
- tool events

### 4.2.4 Kernel loop

- 完整 history + compaction
- plan/memory 注入
- repair loop
- turn/step journal
- checkpoint every tool/step
- stop/budget/timeout

### 4.2.5 Workflow

- `toolset` + `mode`
- `AgentDriver` / `ScriptedDriver`
- `workflow/definitions/research.py`
- 移除生产路径 `DemoOrchestrator`

### 4.2.6 Report migration

- 4 Node full chain 改为多工具
- `demo.source` / `demo.evidence` / `demo.report` 保留为底层工具，但 Node 不再只有一个工具
- report Node 使用 `report.plan/write/check/assemble`
- 100 篇 fulltext demo 重跑

### 4.2.7 Chat

- ConversationSession
- chat workflow
- 复用 Kernel
- 真实 LLM + citation
- 不做 token streaming（可后置）

### 4.2.8 Acceptance

```text
100 papers
fulltext >= 30%
>= 100 claims
>= 5 sections
citation coverage
code + audit
no DemoOrchestrator in production
each agent Node >= 3 tools
context.compact occurs at least once in a long run
```

### 4.2.9 Cleanup

- 删除临时 `demo.orchestrator`
- 删除 `demo.*` 单工具闭环
- 更新 docs/STATUS
- commit

---

## 11. 测试矩阵

```text
tool schema validation
tool output schema validation
tool timeout / cancellation / retry
tool policy deny
parallel-safe scheduler
exclusive barrier
artifact spill
context.inspect / compact
plan.create/update
memory write/search
kernel repair loop
kernel max_steps / max_usd
checkpoint resume
workflow toolset resolution
no DemoOrchestrator import
100-paper fulltext run
chat smoke
```

新增守卫：

```text
test_no_single_tool_agent_node
test_no_demo_orchestrator_in_src
test_tool_output_schema
test_tool_parallel_safety
test_context_compaction
```

---

## 12. 文件布局目标

```text
src/lit_agent_v2/
  contracts/
    tool.py             # ToolSpec/ToolContext/ToolResult
    node.py
    workflow.py
  kernel/
    agent/
      loop.py           # turn/step
      context.py        # assembly + compaction
      scheduler.py      # tool calls
      policy.py
      checkpoint.py
    llm.py
  tools/
    runtime.py          # registry + pipeline
    schema.py
    sets.py             # general/domain toolsets
    general/
      context.py
      plan.py
      memory.py
      test.py
      artifact.py
      verify.py
    domain/
      source.py
      corpus.py
      claims.py
      report.py
      chat.py
  workflow/
    node/
      definition.py
      runner.py
      driver.py
    definitions/
      research.py
      chat.py
  settings/
    config.py
    store.py
  storage/
    db.py
    artifacts.py
    report_store.py
    session_store.py
```

---

## 13. 关键决策

```text
1. Context compaction 是 Kernel 策略 + 可选内部 Tool，不是普通外部工具
2. Tool 分类是 namespace/toolset/policy 元数据，不是两个 Registry
3. Agent Node 至少 3 个工具，不允许单工具 Agent Node
4. Workflow 只依赖 Node/Tool 契约，不 import report
5. Production 不使用 ScriptedDriver/DemoOrchestrator
6. Chat 复用同一 Kernel，但 Phase 4.2 先不实现
7. Settings 分层：env / toml / DB / run snapshot
8. 工具输出必须校验并支持 artifact spill
9. 工具失败返回结构化结果，不终止 turn
10. Repair 是 Kernel 能力，不是 workflow 特判
```

---

## 14. 验收标准

Phase 4.2 完成必须同时满足：

```text
pytest tests/v2 全绿
ruff clean
npm run build 通过
100 篇 fulltext demo 通过
fulltext >= 30%
report complete
每个 agent Node >= 3 tools
至少一个 context.compact 事件
至少一个 plan.update
至少一个 verify.repair
生产路径无 DemoOrchestrator
Chat smoke 走同一 Kernel
```

---

## 15. Commit 序列

```text
feat(T-01): standardize tool contracts and tool runtime
feat(K-02): add kernel turn/step loop with context and planning
feat(W-03): add generic workflow driver and toolsets
feat(R-04): migrate report workflow to multi-tool nodes
feat(C-05): move chat onto the shared kernel
docs(4.2): record acceptance and cleanup
```

---

## 16. 参考

DSH source map:

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

核心借鉴：

```text
typed tool + output contract
tool execution pipeline
parallel-safe / exclusive scheduler
turn/step loop
inbox / steering
structured tool errors
transcript/session persistence
automatic + manual context compaction
```

不照搬：

```text
Cordis plugin system
PTC run_code
full event-sourced session
subagents / multi-agent
browser / computer-use
```
