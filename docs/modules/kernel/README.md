# K · Kernel

> 模块：Kernel
> 版本：2.1（2026-11-02）
> 状态：target；Phase 4.2 优先实现
> 目标：通用 Agent 内核，可独立完成复杂任务

---

## 1. 职责

Kernel 接收 `KernelTask`：

```text
goal
inputs
toolset
output_schema
verifier
policy
```

自主完成：

```text
计划
选择工具
多步骤执行
观察结果
上下文压缩
计划 / 记忆
失败恢复
self-check
repair
输出 artifact
```

Kernel 必须能脱离 Workflow 独立运行。

## 2. 不负责

```text
Workflow 阶段拆分
Node 顺序
报告 / 论文 / claim 等领域逻辑
数据库 / 文件 / HTTP 的直接实现
最终业务验收
```

## 3. 知识边界

Kernel 只认识：

```text
KernelTask
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

Kernel 不知道：

```text
report
paper
claim
section
citation
```

## 4. 契约

```python
Kernel.run(
    task: KernelTask,
    tools: ToolRuntime,
    llm: LLMClient,
    context: KernelContext,
    checkpoint: KernelCheckpoint | None,
) -> KernelResult
```

`KernelResult`：

```text
output
trace
usage
cost
stop_reason
checkpoint
```

## 5. 循环

```text
turn
  → step
    → inbox / steering
    → context assembly
    → context compaction
    → model call
    → tool calls
    → observations
    → checkpoint
  → final / repair / stop
```

## 6. 规则

- Kernel 不 import 领域 workflow。
- Kernel 不判断任务是否为报告。
- 每个工具调用后 / 每个 step 后可 checkpoint。
- 工具失败返回结构化结果，不终止 turn。
- 输出必须经过 output schema / verifier。
- repair 由 Kernel 执行，有预算上限。
- pause 在 step 边界生效。

## 7. 目标文件

```text
kernel/agent/loop.py
kernel/agent/context.py
kernel/agent/scheduler.py
kernel/agent/policy.py
kernel/agent/checkpoint.py
kernel/llm.py
```

## 8. 验收

```text
Kernel A–E 任务通过
无 report 工具也能完成复杂任务
tool 动态选择
plan.update
context.compact
verify.repair
checkpoint / resume
```

详见 [`docs/implementation/PHASE4.2-agent-kernel-tools.md`](../../implementation/PHASE4.2-agent-kernel-tools.md)。
