# Kernel Maturity

> 版本：1.0（2026-11-02）
> 状态：target；S4/S5 只是最小闭环，不是完成
> 目标：先把通用 Kernel 做到可独立承担复杂任务，再改 Workflow

---

## 1. 定位

```text
Workflow 是特制外壳。
Kernel 是通用发动机。
```

如果 Kernel 不成熟，Workflow 只会把不成熟的行为包装成更多固定流程。

所以顺序必须是：

```text
Kernel 完整能力
→ Kernel 真实任务测试
→ Kernel 性能/可观测性验证
→ 才允许改 Workflow
```

---

## 2. 成熟度等级

```text
L0  Skeleton
    能跑一个固定 fake LLM 流程

L1  Functional
    多工具、多步骤、plan/memory/context/repair 可用

L2  Hardened
    并行、取消、checkpoint、持久化、错误分类、日志完整

L3  Benchmarked
    真实 LLM 多任务基准、性能指标、质量门禁
```

当前：

```text
S4 = L0/L1 之间
S5 = 控制流验收
```

目标：

```text
Phase 4.2 完成前达到 L3
```

---

## 3. Kernel 必须补齐的能力

### 3.1 工具调度

```text
parallel_safe 工具并发
exclusive 工具顺序 barrier
bounded pool
结果按 model order 提交
取消时 drain / synthetic error
```

当前 `AgentKernel` 是顺序 for-loop，未使用 `parallel_safe`。

### 3.2 持久化

```text
checkpoint after tool call / step
persist history / plan / memory / cost / usage
resume from checkpoint
crash recovery
```

当前只有进程内 `GeneralState`。

### 3.3 上下文

```text
soft / hard compaction
preserve pinned refs
LLM summary optional
overflow recovery
```

当前 `[compacted]` 是确定性占位。

### 3.4 模型调用

```text
retry + backoff
timeout
rate-limit handling
token / cost accounting
model routing
streaming
```

当前只有一次 `chat_json`。

### 3.5 验证与修复

```text
output schema
code verifier
LLM audit
repair loop
repair budget
failure classification
```

当前只有 schema + callable verifier + 基础 repair。

### 3.6 Node 入口

先做一个**最小 Node 入口**，不修改 Workflow：

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

目的：

```text
让 Kernel 通过一个 Node 入口被调用
但不改现有 Workflow
不进入 report workflow 优化
```

这是 Kernel 独立验收和未来 Workflow 接入之间的桥。

---

## 4. 测试体系

### 4.1 测试层级

```text
L1 单元
  tool spec / schema / state / compaction / error

L2 契约
  KernelTask / KernelResult / ToolContext / event schema

L3 模块
  plan/memory/context/test/verify 工具

L4 集成
  Kernel A–E 脚本任务
  Node entry smoke

L5 真实 LLM
  20–50 个任务，真实模型

L6 压力/性能
  长上下文、多工具、并发、resume、重复运行

L7 回归
  与旧 Node Kernel / 单次 ReAct 对比
```

### 4.2 当前测试

```text
test_tool_runtime.py
test_general_tools.py
test_agent_kernel.py
```

全部是 fake/scripted LLM 的控制流测试。

不能证明：

```text
真实任务成功率
真实工具选择准确率
真实上下文压缩效果
长期运行稳定性
```

### 4.3 必备失败测试

```text
tool timeout
tool exception
tool output schema fail
unknown tool
policy denied
invalid LLM JSON
repeated same tool call
max steps
budget exceeded
context overflow
checkpoint corrupt
cancel mid-tool
model 429 / timeout
```

没有失败测试，不允许进入 Workflow 修改。

---

## 5. Benchmark 任务集

至少 30 个任务，覆盖：

```text
A workspace analysis
B multi-file extraction
C test failure repair
D retrieval + cited brief
E long task with compaction
F tool selection under many tools
G cancellation / resume
H invalid tool args recovery
I output schema repair
J parallel-safe multi-tool
```

每个任务记录：

```text
task_id
success
steps
tool_calls
tool_errors
repair_count
prompt_tokens
completion_tokens
cost_usd
latency_ms
compaction_before
compaction_after
resume_used
final_schema_ok
```

---

## 6. 指标体系

### 6.1 任务

```text
task_success_rate
schema_pass_rate
average_steps
max_steps_hit_rate
repair_rate
repair_success_rate
```

### 6.2 工具

```text
tool_calls_per_task
tool_error_rate
tool_timeout_rate
tool_selection_error_rate
parallel_tool_ratio
```

### 6.3 上下文

```text
prompt_tokens_p50 / p95
completion_tokens_p50 / p95
compaction_count
compaction_ratio
overflow_rate
```

### 6.4 性能

```text
latency_p50 / p95
tool_overhead_p50 / p95
cost_per_task
cost_per_success
steps_per_success
```

### 6.5 稳定性

```text
unhandled_kernel_error_rate
cancel_success_rate
resume_success_rate
checkpoint_restore_success_rate
```

指标不能只看平均；必须记录失败分布。

---

## 7. 日志系统

### 7.1 Event

```json
{
  "schema_version": 2,
  "event_id": "...",
  "run_id": "...",
  "task_id": "...",
  "node_id": "...",
  "step": 3,
  "type": "kernel.tool_result",
  "severity": "info",
  "tool": "fs.read",
  "call_id": "call_3",
  "duration_ms": 12,
  "error_code": null,
  "payload": {}
}
```

### 7.2 Kernel 事件

```text
kernel.started
kernel.step_started
kernel.context_compacted
kernel.plan_updated
kernel.tool_called
kernel.tool_result
kernel.repair
kernel.model_retry
kernel.step_finished
kernel.finished
kernel.failed
kernel.cancelled
```

### 7.3 日志等级

```text
debug    工具参数摘要、上下文选择
info     状态变化、step/tool 完成
warning  重试、压缩、降级
error    任务失败、工具失败、模型失败
```

### 7.4 脱敏

```text
不记录完整 prompt
不记录 API key
不记录论文全文
大内容记录 hash / length / artifact ref
```

---

## 8. 错误系统

### 8.1 分层

```text
E_KERNEL_*    内核循环 / 状态
E_MODEL_*     模型调用
E_TOOL_*      工具执行
E_SCHEMA_*    输入/输出
E_CHECKPOINT_* 持久化
E_POLICY_*    权限
```

### 8.2 常用错误

```text
E_KERNEL_INVALID_ACTION
E_KERNEL_MAX_STEPS
E_KERNEL_TIMEOUT
E_KERNEL_CANCELLED
E_KERNEL_REPAIR_EXHAUSTED
E_KERNEL_OUTPUT_SCHEMA
E_KERNEL_CHECKPOINT
E_MODEL_TIMEOUT
E_MODEL_RATE_LIMIT
E_TOOL_NOT_FOUND
E_TOOL_NOT_ALLOWED
E_TOOL_SCHEMA
E_TOOL_TIMEOUT
E_TOOL_OUTPUT_SCHEMA
E_TOOL_POLICY_DENIED
```

### 8.3 错误结果

错误必须返回结构化字段：

```text
code
message
retryable
attempt
tool
step
details
```

不能只返回异常类名。

---

## 9. Kernel 进入 Workflow 前的门禁

只有全部满足才允许修改 Workflow：

```text
1. Kernel feature checklist 完成
2. Node entry smoke 通过
3. 30+ 真实 LLM benchmark 完成
4. 输出 schema pass >= 99%
5. 简单任务成功率 >= 90%
6. 复杂任务成功率 >= 70%
7. 无未捕获 Kernel 异常
8. resume 成功
9. context compaction 可观测
10. 日志/错误码完整
11. 工具并行可用
12. 没有 report import
```

否则：

```text
不允许开始 report workflow 重构
```

---

## 10. 与 DSH 的差距

| 能力 | DSH | 当前 |
|---|---|---|
| tool contract | 完整 | 基础 |
| tool pipeline | guard/pre/post | 部分 |
| parallel scheduler | 有 | 未接入 Kernel |
| turn/step | 有 | 基础 |
| session persistence | 有 | 无 |
| checkpoint/resume | 有 | 进程内 |
| compaction | 自动 + 手动 | 占位 |
| streaming | 有 | 无 |
| cancellation | 强 | 基础 |
| metrics | 有 | 无 |
| error taxonomy | 完整 | 部分 |
| plugin/scope | 有 | 不需要照搬 |

目标不是复制 DSH 全部，而是把 Kernel 的核心运行质量补齐。

---

## 11. 执行顺序

```text
K1  工具并行调度
K2  持久化 checkpoint / resume
K3  模型重试 / token / cost
K4  上下文压缩 + overflow
K5  NodeKernelAdapter
K6  日志 / 指标 / 错误码
K7  30+ 真实 LLM benchmark
K8  性能优化
K9  门禁通过
      ↓
W1  Workflow core
W2  report workflow
W3  report optimization
W4  chat workflow
```

详细 Phase 计划：

[`PHASE4.2-agent-kernel-tools.md`](implementation/PHASE4.2-agent-kernel-tools.md)
