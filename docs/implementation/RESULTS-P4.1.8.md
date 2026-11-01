# RESULTS · Phase 4.1.8 Demo 100

> Status: done
> Date: 2026-11-01
> Corpus: `D:\lit-agent-store\v2-eval\gold\corpora\agents`
> Output: `D:\lit-agent-store\v2-demo`

---

## 1. Full Chain

```text
source.collect
  demo.source
  → 100 unique papers
  → source.json

evidence.extract
  demo.evidence
  → exact-quote claims
  → evidence.json

report.generate
  demo.report
  → sections
  → report.json + report.md

finalize
  demo.finalize
  → final.json + content_sha
```

The Kernel is the Node runtime. Each Node is a real LLM tool loop; the heavy
100-paper work is executed by deterministic tools so the demo is bounded and
reproducible.

---

## 2. Commands

### Standalone chain

```powershell
cd E:\大学\NUS\EE5003\agent
. .\scripts\env.ps1
uv run python scripts\demo100.py
```

### API full-chain mode

```powershell
. .\scripts\env.ps1
$env:LIT_V2_DB='D:\lit-agent-store\temp\demo100-api.sqlite'
$env:LIT_V2_CORPUS='D:\lit-agent-store\v2-eval\gold\corpora\agents'
$env:LIT_V2_DEMO_CHAIN='full'
$env:LIT_V2_DEMO_OUT='D:\lit-agent-store\v2-demo-api'

uv run uvicorn lit_agent_v2.api.app:create_app `
  --factory --host 127.0.0.1 --port 8000
```

Create a Run through `/api/v2/topics/topic-ai-agents/runs`. The trace contains
four Nodes: `source.collect`, `evidence.extract`, `report.generate`, `finalize`.

---

## 3. Results

```text
papers              100
unique papers       100
claims              174
unique quotes       168
duplicate rate      0.034
sections            13
words               4628
citations           181
fulltext            0 / 100
state               degraded
```

Acceptance:

| Check | Target | Actual | Result |
|---|---|---|---|
| papers | >= 100 | 100 | pass |
| unique | >= 100 | 100 | pass |
| claims | >= 100 | 174 | pass |
| sections | >= 5 | 13 | pass |
| citation coverage | 1 | 181 citations / 174 claims | pass |
| duplicate claim rate | <= 0.1 | 0.034 | pass |
| code verifier | pass | schema verifier for all 4 Nodes | pass |
| audit | pass or degraded | explicit degraded | pass |
| fulltext | >= 30% or explicit degraded | 0%, explicit abstract-only | degraded |

Fulltext is 0 because the local corpus has no `fulltext/*.txt` files. The
overview and report state explicitly say `abstract-only` / `degraded`; this is
the explicit degraded branch, not a hidden full-text claim.

---

## 4. Artifacts

```text
D:\lit-agent-store\v2-demo\
  source.json      100 papers
  evidence.json    174 claims
  report.json      structured report
  report.md        markdown report
  final.json       report path + sha256
```

API run:

```text
run-b8f9efc6dcdb
report_id = run-b8f9efc6dcdb:5d145250...
sections   = 13
n_claims   = 174
words      = 4628
state      = degraded
```

Screenshots:

```text
D:\lit-agent-store\ui-demo100-report2.png
D:\lit-agent-store\ui-demo100-trajectory.png
```

---

## 5. Problems Found and Fixed

### 5.1 Full mode failed with no content_md

`PlatformRunService._run` only checked `content_md`. The full chain stores a
`report_path`; the API raised:

```text
RuntimeError: report node returned no content_md
```

Fix: accept `report_path`, load report JSON, and persist it.

### 5.2 Persisted full report lost sections/claims

`_persist_report` assumed one section and merged Node counts into the report
payload.

Fix: load the report JSON, map `[C#]` references to claim indexes, persist all
sections, claims, and state.

### 5.3 Raw markdown appeared in the UI

`**paper**` and `### heading` were rendered literally by `ReportBody`.

Fix: the deterministic composer now emits plain paragraphs and plain paper
index lines; section headings come from structured sections.

### 5.4 Pause/resume could duplicate a worker

Fixed earlier in Phase 4.1.8:

```text
pause event → Kernel stop at step boundary
WorkflowRunner raises WorkflowInterrupted
resume does not start a second thread
Kernel resumes from checkpoint
demo max_steps 24
```

### 5.5 Resume out_dir

Resume initially passed `resume=True` into the `out_dir` parameter. Fixed by
passing `request.out_dir` and `resume=True` separately.

---

## 6. Caveats

```text
fulltext is 0/100 (corpus limitation)
report prose is deterministic, not LLM-written
audit verifier is not enabled for the demo Nodes
topic scope is not used by demo.report yet
```

This is an end-to-end, reproducible 100-paper demo, not a quality benchmark.
