# RESULTS · Report Runtime Fixes

> Date：2026-11-03
> Scope：SSE、Kernel event mapping、Markdown rendering

---

## 1. SSE `/events`

Added:

```text
GET /api/v2/runs/{run_id}/events
```

Behavior:

```text
poll run_events after seq
emit text/event-stream
id / event / data
heartbeat every 6s
stop on terminal run state
```

Frontend now receives:

```text
run.*
node.*
kernel.*
thinking.summary
section.written / failed
```

Manual probe:

```text
status 200
content-type text/event-stream
```

---

## 2. Kernel event details

`KernelNodeAdapter` now wraps the event sink and attaches `node_id`, so kernel
events belong to the active Node instead of run-level noise.

New events:

```text
thinking.summary
kernel.tool_called
kernel.tool_result
```

`kernel.tool_called` includes:

```text
tool
call_id
step
args_preview
```

`kernel.tool_result` includes:

```text
tool
call_id
ok
error_code
summary
```

---

## 3. UI grouping

`TrajectoryTimeline` now maps:

```text
kernel.tool_called + kernel.tool_result → tool card
thinking.summary → folded thinking
kernel.step_started / checkpoint → hidden
section.written / failed → section progress only
```

Tool cards show:

```text
tool name
call_id
step
args preview
result / error
```

---

## 4. Markdown

Added dependencies:

```text
marked
dompurify
```

`ReportBody.vue` now:

```text
marked.parse()
DOMPurify.sanitize()
walk text nodes for [C#]
replace known citations with buttons
render HTML
```

Supports:

```text
headings
paragraphs
lists
tables
code blocks
blockquotes
links
bold / italic
```

Citation buttons still open the paper.

---

## 5. Validation

```text
128 passed
ruff clean
npm run build passed
```

Manual SSE probe:

```text
GET /api/v2/runs/<id>/events → 200
kernel.tool_called arrives with args_preview
kernel.tool_result arrives with summary
node_id is populated
```


---

## 6. Write failures and format template

Historical failed run:

```text
report.write_next_section → E_TOOL_EXCEPTION:TypeError
```

Cause:

```text
old context-handler path passed the tool context incorrectly
```

This was a code bug, not a model/prompt issue. It is covered by the current
section cursor tests and a fresh 100-paper run.

Fresh run:

```text
sections       23
retries        5
fallback       2
failed         0
quality        passed
audit          accepted
```

Template:

```text
docs/modules/research/REPORT-TEMPLATE.md
REPORT_TEMPLATE in tools/packs/report.py
```

Prompt now includes:

```text
At a Glance
Papers N-M with **paper_id**
Cross-Paper Synthesis
Paper Index
body only, no section heading
one paragraph per paper
```
