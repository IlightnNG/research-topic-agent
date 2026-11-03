# RESULTS · Phase 4.2 Final

> Status：complete
> Date：2026-11-03
> Architecture：Generic AgentKernel + specialized report workflow

---

## 1. Final result

```text
papers             100
fulltext           98
claims             196
sections           23
word_count         4838–5204
state              complete
citation_coverage  1.0
quality gate       passed
LLM audit          accepted
API pause/resume   succeeded
```

Report:

```text
D:\lit-agent-store\v2-report-v2-hard-audit\report.md
D:\lit-agent-store\v2-report-v2-hard-audit\report.json
```

---

## 2. Kernel

```text
AgentKernel
ToolRuntime
parallel scheduler
checkpoint / resume
context compaction
plan / memory / artifacts
model retry / cost
LLM audit hook
```

L3 gate:

```text
30 simple real tasks
14 complex real tasks
8 concurrent soak
audit repair
L3 gate passed
```

Kernel 不 import report / paper / claim。

---

## 3. Report workflow

```text
source.collect
evidence.extract
report.plan
report.write
report.audit_finalize
```

每个 Node：

```text
独立 toolset
output schema
budget
stage verifier
>= 3 tools
```

`report.write` 使用 Node-level section loop：

```text
section_status
→ write_next_section
→ ...
→ assemble_v2
```

section 文件：

```text
out_dir/sections/{section_id}.json
```

---

## 4. Quality

Deterministic gate：

```text
papers >= 100
fulltext >= 35 或 degraded
claims >= 100
sections >= 10
word_count 3500–8000
citation_coverage = 1.0
empty sections = 0
reference problems = 0
```

LLM audit：

```text
compact summary audit
explicit reject -> hard fail
audit unavailable -> fail-open + audit.status=unavailable
```

---

## 5. API / CLI

CLI：

```bash
python -m lit_agent_v2.interface.cli report-v2 \
  --corpus D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext \
  --out D:\lit-agent-store\v2-report-v2
```

API：

```text
LIT_V2_WORKFLOW=report-v2
Phase 4.2 默认
```

Pause / resume：

```text
real API probe passed
no duplicate report
```

---

## 6. UI

```text
5 Node progress
section progress
quality gate badge
failed section retry
```

Build：

```text
npm run build passed
```

---

## 7. Runtime hardening

```text
SSE /events
kernel.tool_called + thinking.summary
markdown marked + DOMPurify
paper title links
online source mode
dynamic quality thresholds
default paper limit = 20
```

## 8. Cleanup

Removed：

```text
src/lit_agent_v2/demo/orchestrator.py
src/lit_agent_v2/demo/__init__.py
scripts/demo100.py
CLI demo100 command
production DemoOrchestrator branch
```

Legacy compatibility：

```text
single-node report flow remains only for old tests
```

---

## 9. Tests

```text
128 passed
ruff clean
npm run build passed
```

---

## 10. Deferred

```text
Qdrant
Kuzu
RAG
Chat
D 盘 root guard
remaining 2/100 fulltext
audit calibration
```

See [TODO.md](../TODO.md).
