# RESULTS · Phase 4.2 L3 Gate

> Status: passed
> Date: 2026-11-02
> Decision: Workflow work is now unblocked

---

## 1. Gate Inputs

Simple benchmark:

```text
30 tasks
real DeepSeek
general tools only
```

Complex benchmark:

```text
14 tasks
2–4+ tools per task
trace-aware audit + automatic repair
```

Soak:

```text
8 real concurrent tasks
concurrency 4
```

---

## 2. Results

### Simple

```text
success      30 / 30
schema       30 / 30
tool errors  0
cost         $0.03749
latency p50  2.53 s
latency p95  4.39 s
```

### Complex

```text
success      12 / 14 = 85.7%
audit accepted 13 / 14 = 92.8%
audit failures 4
audit repairs 3
repairs      4
tool errors  0
cost         $0.03181
latency p50  8.67 s
latency p95  22.73 s
```

Failures:

```text
read-two-summarize:
  audit rejected twice; repair exhausted

plan-replan:
  audit accepted, but final plan verification failed
```

These are real quality failures, not hidden.

### Soak

```text
tasks        8
concurrency  4
success      8 / 8
latency p50  2.27 s
latency p95  2.52 s
cost         $0.00692
```

Total measured cost:

```text
$0.07622
```

---

## 3. Gate Checks

| Check | Target | Actual | Pass |
|---|---|---|---|
| simple success | >=90% | 100% | yes |
| complex success | >=70% | 85.7% | yes |
| simple schema | 100% | 100% | yes |
| audit accepted | >=70% | 92.8% | yes |
| audit repair used | >0 | 3 | yes |
| soak success | 100% | 100% | yes |
| cost measured | yes | $0.076 | yes |

Output:

```text
D:\lit-agent-store\l3-gate.json
```

```json
{"passed": true}
```

---

## 4. What was added

```text
trace-aware `trace_auditor` on KernelTask
automatic audit-triggered repair
audit_repair_successes metric
harder complex tasks
real-LLM concurrent soak
pricing / real cost
L3 gate script
```

Files:

```text
src/lit_agent_v2/kernel/agent/audit.py
src/lit_agent_v2/kernel/agent/task.py
src/lit_agent_v2/kernel/agent/loop.py
benchmarks/kernel_complex_bench.py
benchmarks/kernel_soak.py
benchmarks/l3_gate.py
```

---

## 5. Caveats

```text
complex success is 85.7%, not 100%
audit still rejected 4 times
one audit-approved task failed deterministic verification
14 complex tasks are not a broad quality benchmark
cost is peak DeepSeek Flash pricing
```

The gate passed against the defined thresholds, but the kernel is not perfect.

---

## 6. Decision

```text
L3 gate: PASSED
Workflow: unblocked
```

Next:

```text
S10 Workflow core + report shell
```

No Workflow code was changed during this benchmark phase.
