# Kernel Optimization · DSH-informed

> 日期：2026-11-01
> 目标：参考 DSH agent-loop 的机制，优化 Node Platform Kernel
> 范围：`kernel/node/loop.py`
> 原则：借鉴机制，不复制 DSH 的完整运行时

---

## 1. DSH 参考来源

本地 checkout：

```text
D:\DeepseekHarness\deepseek-harness\
```

主要文件：

```text
packages/core/agent-loop/src/agent.ts
packages/core/agent-loop/src/tool-calls.ts
packages/core/agent-loop/src/assistant-stream.ts
packages/core/agent-loop/README.md
packages/compaction/compaction-tool-result-pruner/src/index.ts
```

公开来源：

- [DeepSeek Harness agent-loop README](https://github.com/deepseek-ai/DeepSeek-Harness/blob/HEAD/packages/core/agent-loop/README.md?plain=1#1)
- [DeepSeek Harness repository](https://github.com/deepseek-ai/DeepSeek-Harness)
- [dsh-fast-loop](https://github.com/Jaylor-Wang/dsh-fast-loop#1)

---

## 2. DSH 中值得借鉴的点

### 2.1 一个 step 可以有多个 tool calls

DSH：

```text
assistant message
  → tool call A
  → tool call B
  → tool result A
  → tool result B
  → next step
```

不是：

```text
one LLM call → one tool
```

### 2.2 tool call 有稳定 id

每次调用：

```text
call_id
name
args
result
```

tool result 与 call id 配对，便于回放、恢复和审计。

### 2.3 并行/串行调度

DSH：

```text
parallel-safe calls → bounded pool
exclusive calls     → barrier
```

工具是否有副作用决定调度方式。

### 2.4 结果裁剪

DSH `compaction-tool-result-pruner`：

```text
thresholdChars
headChars
tailChars
[... tool result middle pruned ...]
```

大工具结果不直接塞入上下文。

### 2.5 step checkpoint

DSH 以 durable session log 记录：

```text
step/start
assistant/message
tool/call
tool/result
step/end
```

恢复来自日志，而不是重新调用 LLM。

### 2.6 有界重试

DSH 将 request error 交给 `agent/request-error` waterfall，由策略决定是否 retry；不是无限循环。

---

## 3. 当前实现已采纳

### 3.1 多 tool calls

新 action schema：

```json
{
  "action": "tool",
  "calls": [
    {"id": "call_1", "name": "source.search", "args": {}},
    {"id": "call_2", "name": "corpus.stats", "args": {}}
  ]
}
```

兼容旧的单工具格式：

```json
{"action": "tool", "tool": "echo", "args": {}}
```

### 3.2 call id

每个 call 有 id：

```text
call_{step}_{index}
```

trace/history 都记录 call_id。

### 3.3 并行调度

```text
all calls side_effect=False → ThreadPoolExecutor
any side_effect=True        → 顺序执行
```

上限：

```text
max_parallel_tools = 4
```

### 3.4 工具输出裁剪

```text
max_tool_chars = 4000
```

超过后：

```json
{
  "truncated": true,
  "chars": 12000,
  "preview": "head... [... tool output pruned ...] ...tail"
}
```

tool result 全文不进模型上下文。

### 3.5 重试

```text
LLM exception.retryable == True
  → 最多 max_retries
  → kernel.retry 事件
```

非 retryable 或耗尽 → failed。

### 3.6 per-call checkpoint + journal

每次 tool result 后写 checkpoint，并在 journal 中记录：

```text
turn.started
step.started
steering.consumed
assistant.tool_calls
assistant.final
tool.result
context.compacted
step.finished
kernel.finished
```

checkpoint 包含：

```text
step
history
trace
cost_usd
usage
journal
stop_reason
```

### 3.7 streaming

Kernel 支持：

```python
kernel.run(..., on_delta=callback)
```

如果 LLM 实现 `stream_json`：

```text
DeepSeek SSE delta
  → on_delta
  → assistant.delta event
  → final JSON
```

没有 `stream_json` 时回退 `chat_json`。

### 3.8 inbox / steering

```python
kernel.steer("use the stricter quote")
```

steering 在下一个 step boundary 注入：

```text
steering.consumed
steering: [...]
```

不会打断正在进行的 tool call。

### 3.9 context compaction

当 history 超过 `max_history_chars`：

```text
旧 tool outputs → {"truncated": true, "reason": "history_compacted"}
保留最近 6 条消息
journal: context.compacted
```

这是确定性 compaction，不是 LLM summary。

### 3.10 event log

Kernel 同时维护：

```text
journal（durable，进入 checkpoint）
EventPort（运行时可订阅）
```

journal 是 per-node 的会话日志雏形，不引入 DSH session projection。

---

## 4. 仍未采纳

```text
hook / waterfall / plugin pipeline
LLM compaction summary
subagent spawning
session projection / replay store
PTC / run_code
inbox wake / turn driver
```

这些不影响当前 Node 的 tool loop。

当前 Node Kernel 只需要：

```text
NodeContext
ToolRegistry
LLM
Checkpoint
```

---

## 5. 当前限制

```text
streaming 依赖 LLM 实现 stream_json
context compaction 是确定性裁剪，不是 token 计量
steering 只在 step boundary 生效
无跨 step tool-call recovery
并行 side-effect 仍被禁止
无独立 session store/projection
```

---

## 6. 测试

```text
tests/v2/test_kernel_node_loop.py
tests/v2/test_kernel_invariants.py
tests/v2/test_kernel_tool_integration.py
tests/v2/test_llm_stream.py
```

覆盖：

- tool → final
- multiple calls in one step
- unauthorized tool
- budget
- no-progress
- max_steps
- cancel
- resume checkpoint
- tool output pruning
- retryable LLM error
- journal / per-call checkpoint
- steering inbox
- history compaction
- streaming callback
- SSE transport
- trace / call-id invariants

当前总门禁：

```text
pytest tests/v2   123 passed
ruff              clean
```

---

## 7. 结论

本次优化借鉴了 DSH 的：

```text
多 tool call
call id
并行/串行区分
tool result pruning
bounded retry
streaming callback
inbox/steering
deterministic compaction
journal / per-call checkpoint
```

但没有复制 DSH 的：

```text
session projections
hook/waterfall/plugin
LLM summary compaction
subagents
PTC
```

目标是让 Kernel 能独立完成一个 Node 的工具任务，而不是重新实现 DSH 全栈。
