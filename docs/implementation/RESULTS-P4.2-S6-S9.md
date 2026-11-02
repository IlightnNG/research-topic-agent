# RESULTS · Phase 4.2 S6–S9

> Status: S6/S7/S8 implemented; S9 deterministic benchmark only
> Date: 2026-11-02
> Important: this is not L3. Real-LLM benchmark is still pending.

---

## S6 · Kernel completeness

Implemented:

```text
parallel-safe / exclusive tool scheduler
file checkpoint / resume
model retry / backoff
token / cost accumulation
automatic context compaction thresholds
structured stop reasons and error_code
kernel metrics
```

Files:

```text
src/lit_agent_v2/kernel/agent/checkpoint.py
src/lit_agent_v2/kernel/agent/scheduler.py
src/lit_agent_v2/kernel/agent/loop.py
src/lit_agent_v2/tools/general/state.py
```

Scheduler:

```text
parallel_safe calls run in a bounded pool
exclusive calls are barriers
results remain in model order
```

Checkpoint:

```text
FileCheckpointStore
  task_id
  step
  history
  plans
  memory
  usage
  cost
```

Resume:

```text
load checkpoint
restore GeneralState
continue at step + 1
clear checkpoint on final
```

---

## S7 · NodeKernelAdapter

Implemented:

```text
src/lit_agent_v2/kernel/agent/node.py
```

```text
NodeSpec + NodeContext
  → KernelTask
  → AgentKernel.run
  → NodeResult
```

This is a minimal Node entrypoint. It does not modify WorkflowRunner and does
not touch report workflow.

---

## S8 · Observability

Implemented:

```text
src/lit_agent_v2/kernel/agent/observability.py
src/lit_agent_v2/kernel/agent/errors.py
```

Event sink:

```text
MemoryEventSink
JsonlEventSink
```

Kernel events:

```text
kernel.started
kernel.step_started
kernel.context_compacted
kernel.tool_result
kernel.model_retry
kernel.repair
kernel.checkpoint
kernel.finished
```

Metrics in `KernelResult.metrics`:

```text
steps
tool_calls
tool_errors
model_retries
repairs
compactions
prompt_tokens
completion_tokens
cost_usd
```

Error codes:

```text
E_KERNEL_INVALID_ACTION
E_KERNEL_MAX_STEPS
E_KERNEL_TIMEOUT
E_KERNEL_CANCELLED
E_KERNEL_REPAIR_EXHAUSTED
E_KERNEL_OUTPUT_SCHEMA
E_KERNEL_CHECKPOINT
E_KERNEL_BUDGET
E_MODEL_FAILED
E_MODEL_TIMEOUT
E_MODEL_RATE_LIMIT
E_TOOL_*
```

---

## S9 · Benchmark

Harness:

```text
benchmarks/kernel_bench.py
```

30 deterministic cases:

```text
6 templates × 5 seeds
plan / fs / memory / artifact / context / multi-tool
```

Result:

```text
cases        30
success      30
success_rate 100%
tool_errors  0
p50 latency  4.07 ms
p95 latency  7.76 ms
```

Output:

```text
D:\lit-agent-store\kernel-benchmark.json
```

### Important limitation

This benchmark uses `ScriptedLLM`.

It validates:

```text
control loop
tool scheduling
artifact/plan/memory/context
metrics
```

It does **not** validate:

```text
real LLM tool selection
real task success
real token/cost behavior
real latency
report quality
```

So S9 deterministic benchmark is complete, but **L3 benchmark is not achieved**.

---

## Tests

```text
104 passed
ruff clean
```

New test file:

```text
tests/v2/test_kernel_hardening.py
```

Covers:

```text
parallel scheduler
checkpoint/resume
model retry
JSONL event sink
NodeKernelAdapter
```

---

## Remaining before Workflow changes

```text
30+ real LLM tasks
real success / schema pass metrics
real token/cost/latency
persistent metrics store
streaming
LLM audit for kernel
full failure-path matrix
```

Therefore:

```text
S10 Workflow core + report shell: still frozen
```

---

## Next

```text
1. Run real-LLM kernel benchmark (30+ tasks)
2. Add persistent metrics store
3. Add streaming interface
4. Harden failure paths
5. Only then S10 workflow
```
