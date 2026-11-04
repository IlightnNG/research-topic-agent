# RESULTS · Phase 4.2 Complex L3 Benchmark

> Status: early benchmark record; final gate passed in [`RESULTS-P4.2-L3-GATE.md`](../../implementation/RESULTS-P4.2-L3-GATE.md)
> Date: 2026-11-02
> Model: `deepseek-flash`
> Pricing: peak rates from DeepSeek official page

---

## 1. Pricing

Implemented in `LLMConfig`:

```text
input_cost_per_m
output_cost_per_m
off_peak_multiplier
```

DeepSeek Flash peak prices:

```text
input   $0.30 / 1M tokens
output  $1.20 / 1M tokens
off-peak = 0.5x
```

Peak hours used by the client:

```text
01:00–04:00 UTC
06:00–10:00 UTC
Monday–Friday
```

Reference:

https://api-docs.deepseek.com/quick_start/pricing/

---

## 2. Simple real-LLM benchmark

30 tasks, real model, general tools:

```text
cases             30
success           30 / 30
schema_ok         30 / 30
tool_errors       0
steps avg         2.63
tool_calls avg    1.37
prompt tokens     96,146
completion tokens 7,203
cost              $0.03749
latency p50       2.53 s
latency p95       4.39 s
```

Store:

```text
D:\lit-agent-store\kernel-live-30-priced.sqlite
D:\lit-agent-store\kernel-live-30-priced.json
```

---

## 3. Complex multi-step benchmark

10 tasks, 2–4 tools per task:

```text
read + summarize + artifact
plan + write + verify
multi-read + artifact
memory + plan
write + list
plan + complete + read
artifact + verify
memory + search
read two files + summarize
context inspect + plan + artifact
```

Result:

```text
cases             10
success           10 / 10
tool_errors       0
steps avg         3.45
tool_calls avg    2.75
prompt tokens     46,257
completion tokens 3,694
cost              $0.01831
latency p50       3.42 s
latency p95       5.73 s
```

Store:

```text
D:\lit-agent-store\kernel-complex-metrics.sqlite
D:\lit-agent-store\kernel-complex.json
```

---

## 4. LLM audit quality

Auditor:

```text
LLMAuditor
  scores relevance / grounding / completeness / clarity
  sees final output + tool trace
```

Result:

```text
audit accepted    7 / 10
audit rejected    2 / 10
audit error       1 / 10
```

Failures were real quality signals:

```text
summary claimed artifact path that differed from hashed path
final summary omitted actual content
one audit response was invalid JSON
```

This is not yet an integrated repair loop in the benchmark.
`repairs` metric is 0 because audit is run after the task.

---

## 5. Long / concurrency / crash stress

Tests:

```text
tests/v2/test_kernel_stress.py
```

Covered:

```text
100-message history → automatic compaction
16 concurrent kernels → all final
cancel after first tool → checkpoint saved
new kernel resumes from checkpoint → final
corrupt checkpoint → safely ignored
```

Result:

```text
3 passed
```

---

## 6. Full tests

```text
117 passed
ruff clean
```

---

## 7. L3 gate

| Gate | Target | Actual | Result |
|---|---|---|---|
| simple success | >= 90% | 100% | pass |
| complex success | >= 70% | 100% | pass |
| schema pass | >= 99% | 100% | pass |
| tool errors | low | 0 | pass |
| cost measured | yes | $0.0558 total | pass |
| latency measured | yes | p95 5.73s complex | pass |
| audit accepted | target TBD | 70% | partial |
| audit repair loop | working | not integrated | fail |
| long/concurrency/crash | pass | pass | pass |

### Decision

```text
This early run: 10 tasks, audit 7/10
Final gate: 14 tasks, audit 13/14, passed
Workflow: unblocked by final gate
```

Reason:

```text
audit accepted only 7/10
audit failure not automatically repaired
complex tasks are still narrow
no streaming UI / long-running production soak
```

So we do **not** start Workflow yet.

---

## 8. Next

```text
1. Integrate auditor into KernelTask with trace-aware repair
2. Improve audit JSON reliability
3. Add 10+ harder multi-step tasks
4. Add long-running soak and parallel real-LLM test
5. Re-run L3 gate
6. Only then start Workflow core + report shell
```
