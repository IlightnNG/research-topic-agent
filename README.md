# lit-agent v2

Literature-research system built around:

```text
Workflow = ordered Node chain
Node = goal + tools + inputs + output schema + verifier + budget
Kernel = Node-local LLM ReAct
Tool = all external I/O
Verifier = code check + LLM audit
```

The legacy report workflow, old kernel, `run_shell`, old API and old tests have
been removed. Platform-only code is the current baseline.

---

## Current status

Phase 4.1 is complete.

```text
Node contracts / workflow runner / kernel        done
ToolRegistry + verifier                          done
report Node + API + Vue frontend                 done
100-paper full-chain demo                         done
legacy cleanup                                   done
```

Full-chain demo:

```text
100 papers
35 / 100 with full text
186 exact-quote claims
13 report sections
4991 words
state = complete
```

Full text was obtained from PDFs for 35 papers. The remaining 65 use abstracts.

---

## Layout

```text
src/lit_agent_v2/
  api/            platform FastAPI app
  interface/      topics, runs, router, CLI
  workflow/       Node chain runner + definitions
  kernel/         Node-local ReAct loop + LLM client
  tools/          ToolRegistry + source/corpus/claims/report/demo tools
  verify/         code + audit verifier
  research/       corpus, claims, PDF, OpenAlex utilities
  storage/        SQLite + report persistence
  domains/chat/   local-evidence chat
  evaluation/     standalone evaluation utilities
tests/v2/         platform tests + cleanup guard
web/              Vue 3 frontend
docs/             architecture, contracts, design, implementation results
```

---

## Run

```powershell
. .\scripts\env.ps1
uv run pytest -q tests/v2
uv run ruff check .
uv run uvicorn lit_agent_v2.api.app:create_app --factory --port 8000
```

API:

```text
http://127.0.0.1:8000/api/v2/health
http://127.0.0.1:8000/api/v2/topics
```

Full chain is the default. Set `LIT_V2_DEMO_CHAIN=single` only for the old
single-Node compatibility profile.

---

## Web

```powershell
cd web
npm install
$env:VITE_USE_MOCK='false'
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`.

Docs:

- [`docs/design/README.md`](docs/design/README.md)
- [`docs/design/FRONTEND.md`](docs/design/FRONTEND.md)
- [`docs/design/DEV-RUNBOOK.md`](docs/design/DEV-RUNBOOK.md)
- [`docs/design/TRAJECTORY-UX.md`](docs/design/TRAJECTORY-UX.md)

---

## 100-paper demo

Prepare full text once:

```powershell
uv run python scripts\prepare_fulltext.py --target 35
```

Run standalone:

```powershell
uv run python scripts\demo100.py
```

Or use the API with:

```powershell
$env:LIT_V2_CORPUS='D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext'
$env:LIT_V2_DEMO_OUT='D:\lit-agent-store\v2-demo-api'
```

See [`docs/implementation/RESULTS-P4.1.8.md`](docs/implementation/RESULTS-P4.1.8.md).

---

## Data

Live data and archives stay outside the repository:

```text
D:\lit-agent-store\
```

---

## Rule

No legacy imports. No compatibility layer. No dual runtime.
