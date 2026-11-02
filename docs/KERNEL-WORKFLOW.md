# Kernel / Workflow Architecture

> 版本：1.0（2026-11-02）
> 状态：target architecture
> 范围：Kernel、Workflow、Tools 的边界
> 相关：`docs/ARCHITECTURE.md`、`docs/implementation/PHASE4.2-agent-kernel-tools.md`

---

## 1. 一句话

```text
Kernel 是通用 Agent 发动机。
Workflow 是特制任务外壳。
```

不是：

```text
通用 Workflow + 领域 Profile
```

---

## 2. 两层结构

```text
┌─────────────────────────────────────────────┐
│ Interface / API / UI / CLI                  │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│ Workflow Layer（特制）                      │
│                                             │
│ report workflow                             │
│   source.collect → evidence.extract         │
│   → report.generate → finalize              │
│                                             │
│ chat workflow                               │
│   retrieve → answer → verify                │
│                                             │
│ research / evaluation workflow              │
└─────────────────────────────────────────────┘
                    │ 每个 Node 调用 Kernel
┌─────────────────────────────────────────────┐
│ Kernel Layer（通用）                        │
│                                             │
│ KernelTask                                  │
│ turn / step                                 │
│ context assembly / compaction                │
│ plan / memory                               │
│ tool scheduler                              │
│ verify / repair                             │
│ checkpoint / cancel                         │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│ Tool Layer                                  │
│ general tools + domain tools                │
└─────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────┐
│ Storage                                     │
│ run / node / session / artifact / report    │
└─────────────────────────────────────────────┘
```

---

## 3. Kernel：通用能力

Kernel 不知道：

```text
report
paper
claim
section
citation
```

Kernel 接收：

```python
KernelTask(
    task_id,
    goal,
    inputs,
    toolset,
    output_schema,
    verifier,
    policy,
)
```

Kernel 自主完成：

```text
计划
选择工具
多步骤执行
观察结果
压缩上下文
失败恢复
自验证
repair
输出 artifact
```

Kernel 必须能独立运行：

```text
没有 report workflow
没有 report tool
只给通用工具和一个目标
Kernel 也能完成任务
```

Kernel 的核心循环：

```text
turn
  → step
    → consume inbox / steering
    → assemble context
    → compact if needed
    → model call
    → tool calls
    → observations
    → checkpoint
  → final / repair / stop
```

---

## 4. Workflow：特制约束

Workflow 负责：

```text
大任务拆解
阶段顺序
阶段输入/输出
阶段工具集
阶段验收
重试 / 暂停 / 人工确认
并行
长时间运行恢复
```

Workflow 不负责：

```text
LLM 循环
工具执行
上下文压缩
通用 repair
```

Workflow 是领域相关的：

```text
report workflow
  source.collect
  evidence.extract
  report.generate
  finalize

chat workflow
  retrieve
  answer
  verify
```

它们共享同一 Kernel，但流程不同。

---

## 5. Node 的定位

```text
Node = Workflow 的阶段
Node ≠ Kernel 的领域类型
```

```text
NodeSpec
  goal
  inputs
  toolset
  output schema
  verifier
  budget
       │
       ▼
KernelTask
```

一个 Node 至少应有：

```text
多个可用工具
context.* / plan.* 之一
明确的输出 schema
阶段 verifier
```

不允许：

```text
一个 Agent Node 只绑定一个工具
Node 的流程由代码写死
```

---

## 6. Tools：通用 + 领域

一个 `ToolRuntime`，通过 metadata 分类：

```text
general:
  context.inspect
  context.compact
  plan.*
  memory.*
  artifact.*
  fs.*
  test.run
  verify.*

domain:
  source.*
  corpus.*
  claims.*
  report.*
  chat.*
```

分类用于：

```text
权限
prompt 体积
预算
审计
UI 分组
```

不是：

```text
专用工具 Agent 不能调用
```

每个 Node 只看到自己的 toolset，而不是整个 Registry。

---

## 7. 报告 Workflow 示例

```text
source.collect
  tools:
    source.search
    source.fetch_pdf
    fulltext.extract
    corpus.store
    corpus.dedupe
    context.inspect
    plan.update
  output: SourceArtifact

evidence.extract
  tools:
    corpus.read
    claims.extract
    quote.check
    claims.dedupe
    evidence.stats
    context.compact
  output: EvidenceArtifact

report.generate
  tools:
    report.plan
    report.write_section
    report.check_section
    report.assemble
    citation.check
    context.compact
  output: ReportDraft

finalize
  tools:
    report.persist
    verify.code
    verify.audit
    artifact.get
  output: FinalReport
```

报告优化只改：

```text
workflow 拆分
阶段 prompt
领域工具
领域 verifier
预算
```

不改 Kernel。

---

---

## 8. Kernel 必须先成熟

Kernel 不成熟时，不允许修改 Workflow。

最小 Node 入口：

```python
class KernelNodeAdapter:
    def run(self, node: NodeSpec, context: NodeContext) -> NodeResult:
        task = KernelTask(
            task_id=f"{context.run_id}:{node.id}",
            goal=node.goal,
            inputs=context.inputs,
            output_schema=node.output_schema,
            toolset=node.toolset,
            policy=KernelPolicy(...),
        )
        result = AgentKernel(...).run(task)
        return NodeResult(
            output=result.output,
            trace=result.history,
            usage=result.usage,
            cost_usd=result.cost_usd,
            stop_reason=result.stop_reason,
        )
```

这个入口只用于：

```text
验证 Kernel 输入输出
验证 Node 级调用
验证 checkpoint/metrics/logs
```

不是 Workflow 改造。

Kernel 进入 Workflow 前必须通过：

```text
30+ 真实 LLM 任务
schema pass >= 99%
simple success >= 90%
complex success >= 70%
resume / compaction / tool recovery
完整日志和错误码
```

详见 [`KERNEL-MATURITY.md`](KERNEL-MATURITY.md)。

## 9. 开发顺序

```text
1. Tool 契约与 ToolRuntime
2. 通用工具
3. 通用 Kernel
4. Kernel-only 任务验收
5. WorkflowRunner + 报告 Workflow
6. 报告质量优化
7. Chat Workflow
```

关键门禁：

```text
Kernel 未通过独立任务验收
不得开始报告 Workflow 优化
```

---

## 10. 禁止事项

```text
Kernel import report
Kernel 判断“报告任务”
Workflow 写进 Kernel
DemoOrchestrator 进入生产路径
单工具 Agent Node
用 prompt 伪装流程控制
```

---

## 11. 验收

```text
Kernel A–E 任务通过
每个 Agent Node >= 3 工具
context.compact 至少一次
plan.update 至少一次
verify.repair 至少一次
100 篇 fulltext 报告完成
Chat 复用同一 Kernel
```

详细计划见：

[`docs/implementation/PHASE4.2-agent-kernel-tools.md`](implementation/PHASE4.2-agent-kernel-tools.md)
