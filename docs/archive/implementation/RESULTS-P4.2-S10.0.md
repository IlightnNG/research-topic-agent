# RESULTS · Phase 4.2 S10.0

> Status：5-node report workflow first slice works
> Date：2026-11-03
> Entry：`lit-agent report-v2`
> Note：CLI path is migrated; API path and resume are not yet.

---

## 1. Implemented

### 5 Nodes

```text
source.collect
evidence.extract
report.plan
report.write
report.audit_finalize
```

Each Node has >=3 tools and a domain toolset:

```text
source.collect       4 tools
evidence.extract     5 tools
report.plan          4 tools
report.write         4 tools
report.audit_finalize 5 tools
```

### New files

```text
src/lit_agent_v2/workflow/report_v2.py
src/lit_agent_v2/workflow/report_v2_runtime.py
src/lit_agent_v2/tools/packs/report_v2.py
tests/v2/test_report_v2.py
```

### Entry

```text
python -m lit_agent_v2.interface.cli report-v2 \
  --corpus D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext \
  --out D:\lit-agent-store\v2-report-v2-cli
```

---

## 2. End-to-end Result

Real LLM, 100-paper local corpus:

```text
papers            100
fulltext          35
claims            186
sections          23
word_count        5291
state             complete
citation_coverage 1.0
```

Outputs:

```text
D:\lit-agent-store\v2-report-v2-cli\report.json
D:\lit-agent-store\v2-report-v2-cli\report.md
D:\lit-agent-store\v2-report-v2-cli\final.json
```

All five Nodes:

```text
source.collect        committed
evidence.extract      committed
report.plan           committed
report.write          committed
report.audit_finalize  committed
```

---

## 3. Architecture

```text
WorkflowRunner
  → KernelNodeAdapter
  → AgentKernel
  → ToolRuntime
  → domain tools
```

Kernel does not import report/paper/claim. Node owns:

```text
goal
toolset
output schema
verifier
budget
```

---

## 4. Current Gaps

```text
API path still uses old Kernel + DemoOrchestrator
Node resume / checkpoint not wired in CLI
report.write is a batch domain tool, not one section per agent step
no audit hook in S10 CLI
no Qdrant / Kuzu
```

Therefore S10 is not complete; this is S10.0.

---

## 5. Next

```text
S10.1 API path to KernelNodeAdapter
S10.2 per-section write and local retry
S10.3 Node checkpoint / resume
S10.4 remove DemoOrchestrator from production
S10.5 final quality gate
```
