# Trajectory UX Rules

> Status: implemented
> Scope: Report → Trajectory
> Related: `docs/design/FRONTEND.md`

---

## 1. Problems Found

From a real run:

```text
tool complete appeared as a separate line
thinking summaries consumed many rows
node failure had no visible reason
run.started appeared at the bottom
```

---

## 2. Rules

### 2.1 Tool call and result are one card

A `tool.called` and its matching `tool.result` are paired by `call_id`.

```text
⚙ report.plan                  call_1  Completed
  sections=...
  ✓ 4 sections planned                  120ms
```

Requirements:

```text
result never renders as an unrelated row
tool card shows Running / Completed / Failed
duration and error stay inside the same card
```

### 2.2 Thinking is collapsed by default

Use `<details>`:

```text
✦ Thinking summary                         EXPAND
```

Expanded:

```text
✦ Thinking summary                         EXPAND
  I will keep only claims with exact quotes...
```

No full reasoning text by default.

### 2.3 Node failure reason is visible

Sources:

```text
node.error          from run_nodes.error_code
node.failed.error   event payload
run.failed.error    event payload
```

UI shows:

```text
node header: Failed
inline node error
tool card failure result
Run failed block
```

### 2.4 run.started is at the top

`run.started` is rendered above the node timeline.

`run.finished` / `run.failed` remain below the timeline.

### 2.5 Tool result summary

Backend `Kernel` emits:

```text
summary
duration_ms
```

with `tool.result`, so the tool card can show what completed, not only
"Tool completed".

---

## 3. Backend Changes

```text
Kernel._summary(result)
  → tool.result.summary
  → tool.result.duration_ms
```

```text
PlatformRunService.trace
  → run_nodes.error_code
  → node.error
  → running node becomes failed when run failed
```

```text
DbEvents.emit(run.failed)
  → mark running/verifying/pending nodes failed
```

---

## 4. Frontend Changes

```text
web/src/components/report/TrajectoryTimeline.vue
  pairing by call_id
  thinking details collapsed
  node error display
  run.started top
  run.failed error block
```

```text
web/src/types/index.ts
  NodeTrace.error
  run.started / run.failed event types
```

---

## 5. Verification

Mock GUI:

```text
run.started first      true
thinking open          0
thinking closed        3
tool completed badge   3
```

Failed run:

```text
failed block           1
node error             1
run error text         Verifier rejected the report: 0 claims with exact quotes.
```

Screenshots:

```text
D:\lit-agent-store\ui-trajectory-ux2.png
D:\lit-agent-store\ui-trajectory-failed.png
```


---

## 6. context.compacted is expected

`context.compacted` is emitted by the Kernel when the prompt history exceeds
`max_history_chars`.

For the 10:32 run it fired at steps:

```text
5
6
7
```

That is normal: each step adds tool output, then the next LLM call compacts the
oldest tool results to stay within budget.

It is not a failure. The UI now:

```text
associates the event with the Node
does not render three top-level run rows
shows one note: Context compacted 3× to keep the prompt within budget.
```

Older rows were written with `node_id = NULL`. The trace API now normalizes
those historical rows to the Node that was active at that sequence, so existing
runs also render the compaction note inside the Node. New events are emitted
with the Node id directly.

---

## 7. Duplicate Run succeeded

Cause:

```text
trace event id      run_id:seq
SSE event id        seq
```

The same event was not deduplicated, so `run.finished` rendered twice.

Fix:

```text
SSE event id = run_id:seq
```

Now trace replay and SSE append share the same id.

---

## 8. Why only one Node

The API currently uses:

```text
build_report_demo_workflow
  → one Node: report.generate
```

This is the S6 demo profile. It deliberately puts retrieval, claim extraction,
planning, writing, and persistence inside one Node's tool loop.

The full target chain is:

```text
source.collect
  → evidence.extract
  → report.generate
  → finalize
```

`build_report_workflow` already defines that chain, but the current API demo
still uses the one-node profile. Splitting into multiple Nodes is future work.


---

## 9. Pause / Resume race

Symptom:

```text
run was paused, then resumed
→ a second worker thread started
→ the first thread also kept running
→ two run.started / node.started sequences
→ one thread finished, the other later failed
→ run state was overwritten to failed
```

Root causes:

```text
pause only changed the DB state
the active Kernel did not stop at a step boundary
resume always started a new thread
two threads wrote the same run
```

Fix:

```text
PlatformRunService tracks the active thread per run
pause sets a pause event and asks Kernel to stop at the next step
Kernel returns stop_reason=cancelled
WorkflowRunner raises WorkflowInterrupted
resume does NOT start a second worker if the current one is alive
resume continues from the Kernel checkpoint instead of step 1
runner.run(..., resume=True)
demo max_steps increased from 12 to 24
```

Verification:

```text
create run → pause at step 2 → paused
resume → run.resumed
run succeeded
report_id returned
only one worker / no duplicate run.started
```

---

## 10. Run menu click-outside

The run overflow menu now closes when clicking anywhere outside the Run list.

Implementation:

```text
document click listener
root contains target → keep open
target outside root → menuFor = ""
```

Same behavior is applied to the Chat conversation menu.
