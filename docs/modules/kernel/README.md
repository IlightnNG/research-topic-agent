# K · Kernel

> 模块：Kernel
> 版本：2.0（2026-11-01）
> 状态：target；已有 ReAct 原型，需重写接口
> 目标：执行单个 Node。

---

## 1. 职责

```text
NodeContext
goal prompt
tool allowlist
ReAct loop
tool call / observation
budget / steps / timeout
no-progress
cancel
step checkpoint
NodeResult
```

## 2. 不负责

```text
Workflow 拓扑
Node 顺序
领域 service
数据库/文件/HTTP
Verifier 最终判定
```

## 3. 契约

```python
Kernel.run(
    node: NodeSpec,
    context: NodeContext,
    tools: ToolRegistry,
    llm: LLMClient,
    checkpoint: KernelCheckpoint | None,
) -> NodeResult
```

NodeResult：

```text
output
trace
usage
cost
stop_reason
checkpoint
```

## 4. 目标文件

```text
kernel/loop.py
kernel/context.py
kernel/checkpoint.py
kernel/budget.py
```

## 5. 规则

- 只能调用 Node allowlist 工具；
- 不能改 Workflow；
- 不能直接 import domain；
- 每次工具调用后可 checkpoint；
- no-progress / budget / timeout 必须终止；
- `final` 输出必须符合 Node output schema。

## 6. 验收

```text
fake LLM tool→final
unregistered tool rejected
budget stops
no-progress stops
checkpoint/resume
```

## 7. 当前实现

```text
kernel/node/loop.py
kernel/node/checkpoint.py
kernel/node/ports.py
```

状态：4.1.3 done + DSH-informed optimization；旧 kernel/loop.py 仍在迁移期保留给 Chat。

## 8. Phase docs

```text
K-P01-node-context.md
K-P02-tool-loop-checkpoint.md
```
