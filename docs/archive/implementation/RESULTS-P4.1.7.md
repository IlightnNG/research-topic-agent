# RESULTS · Phase 4.1.7 Frontend / Backend Integration

> Date: 2026-11-01
> Scope: Composition/Interface + Vue real API mode
> Status: passed for topics → run → trace → report → paper; chat basic

---

## 1. Backend Interface

New files:

```text
src/lit_agent_v2/interface/topics.py
src/lit_agent_v2/interface/runs.py
src/lit_agent_v2/interface/router.py
```

Mounted before legacy routes in `api/app.py`, so the frontend's target endpoints
resolve to the platform implementation.

Topic persistence:

```text
topics
  id, direction, description, keywords_json, exclusions_json,
  constraints_json, brief_json, created_at
```

Seed topics:

```text
topic-ai-agents
topic-fpga
topic-rag
```

Run pipeline:

```text
POST /api/v2/topics/{topic}/runs
  → PlatformRunService
  → topic scope injected into Node goal
  → build_report_demo_workflow
  → ToolRegistry(corpus + claims + report tools)
  → Kernel
  → Verifier
  → WorkflowRunner
  → run_events / run_nodes / run_artifacts
  → reports / report_sections / citations
```

Report artifacts are persisted with:

```text
ReportDraft
  title
  content_md
  one section
  claims
```

`ReportStore.get` now attaches `paper_links` from `citations`, so the Vue
ReportViewer can turn `[C1]` into a paper tab.

---

## 2. Frontend Real Mode

```text
web/.env.local
VITE_USE_MOCK=false
```

Vite proxy:

```text
/api → http://127.0.0.1:8000
```

Client adaptations:

```text
GET /runs/{id}/report -> {report_id}
GET /reports/{id}     -> {report, sections}
  → transformed to Vue Report shape
SSE event payload     -> flattened from {payload:{...}}
```

---

## 3. Live E2E

Backend:

```powershell
$env:LIT_V2_DB='D:\lit-agent-store\temp\f17.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\p41-report-experiment'
uv run uvicorn lit_agent_v2.api.app:create_app --factory --port 8000
```

Frontend:

```powershell
$env:VITE_USE_MOCK='false'
npm run dev -- --host 127.0.0.1
```

Observed:

```text
topics = 3
new run = succeeded
trace = report.generate committed, tool.called/tool.result events
report = 247 words, 5 claims
report tab = active
citation click = paper tab opened
chat = conversation + assistant reply
```

Screenshot paths:

```text
D:\lit-agent-store\ui-real-trajectory.png
D:\lit-agent-store\ui-real-report.png
D:\lit-agent-store\ui-real-chat.png
```

---

## 4. Tests

Python:

```text
pytest tests/v2   135 passed
ruff              clean
```

Platform API test:

```text
tests/v2/test_platform_api.py
  topics
  create topic run
  poll run
  trace nodes/events
  report sections/paper_links
  paper metadata
  delete run
```

Frontend:

```text
npm run build     passed
```

Browser smoke:

```text
topics        3
new run       succeeded
tabs          Trajectory | Report
paper tab     opened
chat          real backend reply
```

---

## 5. Known Gaps

```text
pause only checks at Node boundaries
one-node demo cannot pause mid-Node
topic normalization is deterministic, not LLM
report is persisted as one section with headings in markdown
real chat has no token streaming; mock has streaming
PDF reader is iframe + metadata fallback
```

Next:

```text
4.1.8 Demo 100
4.1.9 delete legacy ReportWorkflow/write.py
```
