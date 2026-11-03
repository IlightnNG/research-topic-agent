# RESULTS · Phase 4.2 S6–S9

> Status: S6/S7/S8 implemented; S9 superseded by final L3 gate
> Date: 2026-11-02
> Important: final L3 gate passed; see [`RESULTS-P4.2-L3-GATE.md`](RESULTS-P4.2-L3-GATE.md).

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

### Real LLM benchmark

Harness:

```text
benchmarks/kernel_live_bench.py
```

30 tasks, real DeepSeek, general tools only:

```text
read file
write artifact
create plan
list workspace
write memory
run pytest
```

Result:

```text
cases        30
success      30
success_rate 100%
schema_ok    30 / 30
tool_errors  0
prompt_tokens  95,520
completion_tokens 6,248
cost_usd     0.0 (pricing not configured)
latency_p50  2.58 s
latency_p95  4.69 s
```

Persistent metrics:

```text
D:\lit-agent-store\kernel-live-30.sqlite
D:\lit-agent-store\kernel-live-30.json
```

### Important limitation

The 30 real tasks are intentionally simple: one general tool plus final.

They validate:

```text
real LLM tool selection
real output schema
real tokens / latency
general-tool execution
metrics persistence
```

They do **not** validate:

```text
complex multi-step research
long-running tasks
report quality
complex recovery
```

So S9 real simple and complex execution benchmark is complete; L3 quality gate is not.

See [`RESULTS-P4.2-S9-L3.md`](RESULTS-P4.2-S9-L3.md).

---

## Tests

```text
122 passed
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
complex multi-step real LLM tasks
real cost pricing
streaming end-to-end
LLM audit for kernel
full failure-path matrix
long-running / crash recovery
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
