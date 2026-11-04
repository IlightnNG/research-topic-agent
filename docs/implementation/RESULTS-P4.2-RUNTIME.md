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
docs/REPORT-TEMPLATE.md
REPORT_TEMPLATE in tools/packs/report.py
```

Prompt now includes:

```text
At a Glance
Papers N-M with **paper title**
Cross-Paper Synthesis
Paper Index
body only, no section heading
one paragraph per paper
```


---

## 7. Paper titles and format enforcement

Before:

```text
**W88095936.** ...
```

After:

```text
**[A schematic representation for cognitive tool-using agents.](#paper-W88095936)** ...
```

Rules:

```text
paper IDs are replaced with paper titles
title links use #paper-<paper_id>
ReportBody intercepts #paper-* clicks and opens a paper tab
paper_index is generated deterministically from all evidence papers
paper_analysis falls back to a deterministic title-linked paragraph if
the LLM omits required paper titles
```

Quality on a fresh 100-paper run:

```text
sections  23
words     7005
quality   passed
audit     accepted
```


---

## 8. Source mode / dynamic quality / default 20

Added:

```text
source.collect_online
source.search
source.fetch_pdf
source.fetch_html
```

Request fields:

```text
source_mode = local | online | auto
query
limit
```

UI New Run now exposes:

```text
Source: local / online / auto
Paper limit: default 20
```

Quality thresholds are no longer fixed at 100. They derive from
`target_papers` in `evidence.json`:

```text
target = requested limit
min_papers = target
min_claims = target
min_fulltext = 20% of target
min_sections = based on target
```

20-paper run:

```text
papers             20
fulltext           19
claims             38
sections           7
word_count         1602
state              complete
citation_coverage  1.0
quality gate       passed
audit              accepted
```

Local corpus still does not download; online mode uses OpenAlex search and
downloads open PDF/HTML when available.


---

## 9. UI interaction cleanup

```text
tool input/output folding was reverted to the original full display
thinking summary remains one line and expands on click
tool name / call id remain in the header
paper title links open a paper tab
```

## 10. Final commits

```text
3eb8c03 fix(runtime): add SSE, kernel event detail and markdown renderer
c79227a fix(report): add format template, fold tool IO and improve write prompt
da163b7 fix(report): use paper titles and enforce section format
4e93ef9 feat(report): add online source mode, dynamic quality and paper title links
```
