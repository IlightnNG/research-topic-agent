# RESULTS · Phase 4.1.9 Legacy Cleanup

> Status: done
> Date: 2026-11-01
> Scope: delete legacy report workflow, platform-only API, final Phase 4.1 cleanup.

---

## 1. Deleted

```text
src/lit_agent_v2/run_shell.py
src/lit_agent_v2/cli.py
src/lit_agent_v2/contracts/ports.py
src/lit_agent_v2/workflow/runner.py
src/lit_agent_v2/workflow/verifier.py
src/lit_agent_v2/workflow/definition.py
src/lit_agent_v2/kernel/loop.py
src/lit_agent_v2/kernel/tools.py
src/lit_agent_v2/kernel/checkpoint.py
src/lit_agent_v2/domains/report/
src/lit_agent_v2/storage/artifacts.py
```

Legacy tests:

```text
M1–M6 tests
S1–S8 tests
contract freeze 1.2
boundaries
old API tests
```

---

## 2. Migrated Utilities

```text
domains/report/claim_extractor.py
  → research/claims.py

domains/report/ingest.py
  → research/corpus.py

domains/report/openalex.py
  → research/openalex.py

domains/report/pdf.py
  → research/pdf.py

domains/report/persist.py
  → storage/report_store.py
```

These are data/research utilities, not the old workflow. The old report workflow,
writer, plan, mapper, policy and audit modules were deleted with `domains/report`.

---

## 3. API / CLI

`api/app.py` is now platform-only:

```text
/api/v2/topics
/api/v2/topics/{id}/runs
/api/v2/runs/{id}/trace
/api/v2/runs/{id}/pause
/api/v2/runs/{id}/resume
/api/v2/reports/{id}
/api/v2/conversations/{id}
```

Old `/api/v2/runs` list/create, old HTML page and old `RunShell` routes are gone.

New CLI:

```text
src/lit_agent_v2/interface/cli.py
lit-agent demo100 ...
```

Because `[tool.uv] package = false`, use:

```powershell
uv run python -c "from lit_agent_v2.interface.cli import main; main()" demo100
```

or the standalone script:

```powershell
uv run python scripts/demo100.py
```

---

## 4. Chat

`domains/chat/answer.py` no longer imports the deleted legacy kernel.

It is now a small local-evidence retrieval answerer:

```text
token overlap ranking
top 3 snippets
deterministic citation answer
optional composer hook
```

Chat remains a Phase 5 migration item (real LLM chat / streaming), but it no
longer keeps the old kernel alive.

---

## 5. Contracts

```text
CONTRACT_VERSION = 2.0
SCHEMA_VERSION = 2
CONTRACT_FROZEN_AT = 2026-11-01
```

`CONTRACT_HASH` was recomputed over:

```text
artifacts.py
features.py
node.py
tool.py
verdict.py
report.py
```

Old 1.2 `contracts/ports.py` and its freeze test were deleted.

---

## 6. Verification

```text
pytest tests/v2   84 passed
ruff              clean
npm run build     passed
demo100           ACCEPTANCE PASS
```

Guard test:

```text
tests/v2/test_no_legacy_imports.py
```

It asserts:

```text
no legacy files
no legacy imports in src/ or tests/
```

Demo result remains:

```text
100 papers
174 claims
13 sections
4628 words
degraded (abstract-only corpus)
```

API full-chain smoke after cleanup:

```text
run-16b2eb09c6dc  succeeded
4 Nodes committed
report: 13 sections / 174 claims / 4628 words
```

One earlier LLM finalization attempt returned an invalid action and failed at
`report.generate`; a retry succeeded. This is model stochasticity, not a
cleanup regression. The deterministic demo script remains the canonical
acceptance path.

---

## 7. Phase 4.1 Close

Phase 4.1 is complete:

```text
4.1.0  contracts / module skeleton
4.1.1  Node contracts
4.1.2  Node chain runner
4.1.3  Kernel
4.1.4  Tool registry
4.1.5  Code + audit verifier
4.1.6  report Node
4.1.7  API / Vue integration
4.1.8  100-paper demo
4.1.9  legacy cleanup
```

Commit:

```text
refactor(W-P03): complete phase 4.1 and delete legacy report workflow
```
