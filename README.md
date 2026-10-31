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

- LLM section writing;
- 5–8 high-quality directions on real 100-paper corpora;
- ≥30% full-text coverage;
- report count/claim consistency;
- LLM judge + human gold evaluation;
- production UI.

See [`docs/TODO.md`](docs/TODO.md) for the audit findings, [`docs/modules/README.md`](docs/modules/README.md) for module boundaries, and [`docs/implementation/PHASE4-report-end-to-end.md`](docs/implementation/PHASE4-report-end-to-end.md) for Phase 4.

## Layout

```text
src/lit_agent_v2/
  api/            FastAPI v2
  kernel/         minimal agent kernel
  workflow/       runner, events, verifier
  domains/
    report/       source, evidence, map, write, persist
    chat/         answer, sessions, stream
  metrics/        metric specs, store, gates
  evaluation/     dataset, evaluators, tuner
  storage/        SQLite + content-addressed artifacts
tests/v2/         v2 tests only
docs/             current docs only
```

## Run

```powershell
. .\scripts\env.ps1
uv run pytest -q tests/v2
uv run uvicorn lit_agent_v2.api.app:create_app --factory --port 8001
```

The v2 API is independent of the removed legacy app.

## Report from local corpus

```powershell
uv run python -c "from lit_agent_v2.cli import main; main()" run --topic llm-agents --limit 100 --corpus D:\lit-agent-store\v2-live\corpus
```

## Data

Live data and archives are stored outside the repository:

```text
D:\lit-agent-store\
```

## Rule

No legacy imports. No compatibility layer. No dual runtime. New work goes into `src/lit_agent_v2/` only.
