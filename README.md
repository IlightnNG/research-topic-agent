# lit-agent v2

Greenfield literature-research system. The legacy `lit_agent` package, old graph/report/chat, old tests and old docs have been removed from this repository.

## Current status

This is a **working prototype**, not a completed research system.

What works:

- OpenAlex ingestion + local corpus;
- PDF text extraction;
- source selection;
- evidence + exact-quote claims;
- direction clustering;
- deterministic report assembly and persistence;
- metrics points/spans;
- chat with citations;
- v2 API with async runs, SSE events, pause/resume, report retrieval;
- v2 tests.

What is not done:

- Node/Tool/Verifier platform migration;
- report.generate as agent node;
- demo profile with classification disabled;
- ≥30% full-text coverage on the live corpus;
- usable gold evaluation;
- production UI.

Start with:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — target architecture 2.0;
- [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — Node/Tool/Verifier contracts;
- [`docs/modules/README.md`](docs/modules/README.md) — platform modules and legacy M1–M6 mapping;
- [`docs/STATUS.md`](docs/STATUS.md) — current migration state.

## Layout

```text
src/lit_agent_v2/
  api/            FastAPI v2
  kernel/         ReAct kernel, tools, checkpoint
  workflow/       node chain, runner, state
  tools/          target ToolRegistry
  verify/         target code + audit verifier
  domains/
    report/       source, evidence, map, write, persist
    chat/         answer, sessions, stream
  metrics/        metric specs, store, gates
  evaluation/     dataset, evaluators, tuner
  storage/        SQLite + content-addressed artifacts
tests/v2/         v2 tests only
web/              Vue 3 frontend (F1/F2)
docs/             current docs only
```

## Run

```powershell
. .\scripts\env.ps1
uv run pytest -q tests/v2
uv run uvicorn lit_agent_v2.api.app:create_app --factory --port 8001
```

The v2 API is independent of the removed legacy app.

## Web

The Vue frontend lives in `web/`.

```powershell
cd web
npm install
npm run dev
```

Current scope: F1–F6 (Topics, Report shell, Run list, New Run modal, per-run tabs, Run delete, trajectory + pause/resume, report + paper tabs, Chat, Inspector).
Set `VITE_USE_MOCK=false` to use the real platform API; mock remains the default for UI-only work.

See [`web/README.md`](web/README.md), [`docs/design/FRONTEND.md`](docs/design/FRONTEND.md), and the [local dev runbook](docs/design/DEV-RUNBOOK.md).

## Report from local corpus

```powershell
uv run python -c "from lit_agent_v2.interface.cli import main; main()" demo100 --corpus D:\lit-agent-store\v2-eval\gold\corpora\agents
```

## Data

Live data and archives are stored outside the repository:

```text
D:\lit-agent-store\
```

## Rule

No legacy imports. No compatibility layer. No dual runtime. New work goes into `src/lit_agent_v2/` only.
