# Docs

> 2026-11-01：架构已升级为 Workflow=Node 链 + Kernel + Tools + 双 Verifier。
> 先读 `ARCHITECTURE.md` 2.0 与 `CONTRACTS.md` 2.0 DRAFT；旧 M1–M6 文档为历史记录。

Current documents only.

| Doc | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | target architecture 2.0: Node chain + Kernel + Tools + Verifier |
| [`STATUS.md`](STATUS.md) | current state / next action / handoff |
| [`TODO.md`](TODO.md) | standardized TODO registry |
| [`CONTRACTS.md`](CONTRACTS.md) | Node/Tool/Verifier contracts (2.0 DRAFT) |
| [`CONVENTIONS.md`](CONVENTIONS.md) | module/phase/commit/TODO naming |
| [`DECISIONS.md`](DECISIONS.md) | architecture decisions that must not be re-litigated |
| [`ERRORS.md`](ERRORS.md) | error code registry |
| [`LOGGING.md`](LOGGING.md) | event/log contract |
| [`TESTING.md`](TESTING.md) | test levels/fixtures/gates |
| [`implementation/PHASE4-report-end-to-end.md`](implementation/PHASE4-report-end-to-end.md) | historical Phase 4 plan |
| [`implementation/PHASE4.1-node-platform-migration.md`](implementation/PHASE4.1-node-platform-migration.md) | Node platform migration plan |
| [`implementation/BASELINE-P4.1.md`](implementation/BASELINE-P4.1.md) | pre-migration baseline |
| [`implementation/KERNEL-OPTIMIZATION.md`](implementation/KERNEL-OPTIMIZATION.md) | DSH-informed kernel optimization |
| [`implementation/TOOLS-DSH-DESIGN.md`](implementation/TOOLS-DSH-DESIGN.md) | DSH-informed tool registry design |
| [`implementation/RESULTS-KERNEL-TEST.md`](implementation/RESULTS-KERNEL-TEST.md) | kernel + tools test matrix and live smoke |
| [`implementation/RESULTS-VERIFY-TEST.md`](implementation/RESULTS-VERIFY-TEST.md) | code + audit verifier test matrix |
| [`implementation/RESULTS-REPORT-KERNEL.md`](implementation/RESULTS-REPORT-KERNEL.md) | kernel-only report feasibility experiment |
| [`implementation/RESULTS-S6-REPORT-NODE.md`](implementation/RESULTS-S6-REPORT-NODE.md) | S6 report node E2E and live run |
| [`modules/README.md`](modules/README.md) | platform module map + legacy M1–M6 mapping |
| [`implementation/RESULTS-P3.6-LIVE.md`](implementation/RESULTS-P3.6-LIVE.md) | real OpenAlex run + audit |
| [`implementation/RESULTS-M1-P01.md`](implementation/RESULTS-M1-P01.md) | M1-P01 result |
| [`implementation/RESULTS-M3-P01.md`](implementation/RESULTS-M3-P01.md) | M3-P01 result |
| [`implementation/RESULTS-M2-P01.md`](implementation/RESULTS-M2-P01.md) | M2-P01 result |
| [`implementation/RESULTS-M4-P01.md`](implementation/RESULTS-M4-P01.md) | M4-P01 result |
| [`implementation/RESULTS-M4-P02.md`](implementation/RESULTS-M4-P02.md) | M4-P02 result |
| [`implementation/RESULTS-M5-P01.md`](implementation/RESULTS-M5-P01.md) | M5-P01 result |
| [`implementation/RESULTS-M5-P02.md`](implementation/RESULTS-M5-P02.md) | M5-P02 result |
| [`implementation/RESULTS-M5-P02-CASE1.md`](implementation/RESULTS-M5-P02-CASE1.md) | case-001 AI prelabel sample analysis |
| [`implementation/RESULTS-M6-P01.md`](implementation/RESULTS-M6-P01.md) | M6-P01 result |
| [`modules/evaluation/GOLD-ANNOTATION.md`](modules/evaluation/GOLD-ANNOTATION.md) | 300-paper gold annotation workflow |

Module docs:

```text
modules/workflow/
modules/kernel/
modules/tools/
modules/verify/
modules/storage/
modules/interface/
modules/research/
modules/evaluation/
modules/composition/
```

Legacy M1–M6 phase docs are archived at
`D:\lit-agent-store\legacy-archive-20261101\docs-modules\`.

Archived legacy docs/code: `D:\lit-agent-store\legacy-archive-20261031\`.
