# Docs

> 2026-11-01：架构已升级为 Workflow=Node 链 + Kernel + Tools + 双 Verifier。
> 先读 `ARCHITECTURE.md` 2.0 与 `CONTRACTS.md` 2.0；旧实现记录见 `docs/archive/`。

Current documents only.

| Doc | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | system architecture: generic Kernel + specialized Workflow |
| [`KERNEL-WORKFLOW.md`](KERNEL-WORKFLOW.md) | canonical Kernel / Workflow two-layer boundary |
| [`KERNEL-MATURITY.md`](KERNEL-MATURITY.md) | kernel maturity, benchmark, metrics, logging, errors, workflow gate |
| [`STATUS.md`](STATUS.md) | current state / next action / handoff |
| [`TODO.md`](TODO.md) | standardized TODO registry |
| [`CONTRACTS.md`](CONTRACTS.md) | Node/Tool/Verifier contracts, 2.0 frozen |
| [`CONVENTIONS.md`](CONVENTIONS.md) | module/phase/commit/TODO naming |
| [`DECISIONS.md`](DECISIONS.md) | architecture decisions that must not be re-litigated |
| [`ERRORS.md`](ERRORS.md) | error code registry |
| [`LOGGING.md`](LOGGING.md) | event/log contract |
| [`TESTING.md`](TESTING.md) | test levels/fixtures/gates |
| [`design/README.md`](design/README.md) | design docs index and frontend status |
| [`design/FRONTEND.md`](design/FRONTEND.md) | Vue report/chat frontend design |
| [`design/DEV-RUNBOOK.md`](design/DEV-RUNBOOK.md) | local frontend/backend startup and manual test |
| [`design/TRAJECTORY-UX.md`](design/TRAJECTORY-UX.md) | trajectory UX rules and failure visibility |
| [`../web/README.md`](../web/README.md) | Vue frontend F1–F6 implementation |
| [`implementation/README.md`](implementation/README.md) | active implementation docs index |
| [`implementation/PHASE4.2-agent-kernel-tools.md`](implementation/PHASE4.2-agent-kernel-tools.md) | next phase: generic Agent Kernel, tools, workflow |
| [`implementation/PHASE4.1-node-platform-migration.md`](implementation/PHASE4.1-node-platform-migration.md) | completed Node platform migration |
| [`implementation/RESULTS-P4.1.8.md`](implementation/RESULTS-P4.1.8.md) | 100-paper fulltext full-chain result |
| [`implementation/RESULTS-P4.2-S0-S2.md`](implementation/RESULTS-P4.2-S0-S2.md) | S0–S2: tool contracts and ToolRuntime |
| [`implementation/RESULTS-P4.2-S3-S5.md`](implementation/RESULTS-P4.2-S3-S5.md) | S3–S5: general tools, AgentKernel, A–E acceptance |
| [`implementation/RESULTS-P4.2-S6-S9.md`](implementation/RESULTS-P4.2-S6-S9.md) | S6–S9: hardening, node entry, observability, benchmark |
| [`implementation/RESULTS-P4.2-S9-L3.md`](implementation/RESULTS-P4.2-S9-L3.md) | early real-LLM benchmark record |
| [`implementation/RESULTS-P4.2-L3-GATE.md`](implementation/RESULTS-P4.2-L3-GATE.md) | final L3 gate result |
| [`implementation/RESULTS-P4.2-S10.0.md`](implementation/RESULTS-P4.2-S10.0.md) | S10.0: 5-node report CLI |
| [`implementation/RESULTS-P4.2-S10.1-S10.3.md`](implementation/RESULTS-P4.2-S10.1-S10.3.md) | S10.1–S10.3: API, per-section, resume |
| [`implementation/RESULTS-P4.2-S10.4-S10.7.md`](implementation/RESULTS-P4.2-S10.4-S10.7.md) | S10.4–S10.7: demo removal, quality gate, cleanup |
| [`implementation/RESULTS-P4.2-S10.2b.md`](implementation/RESULTS-P4.2-S10.2b.md) | S10.2b: Node-level section loop |
| [`implementation/RESULTS-P4.2-4.2.11.md`](implementation/RESULTS-P4.2-4.2.11.md) | 4.2.11: section quality metrics |
| [`implementation/RESULTS-P4.2.md`](implementation/RESULTS-P4.2.md) | Phase 4.2 final result |
| [`implementation/RESULTS-P4.1.9.md`](implementation/RESULTS-P4.1.9.md) | legacy cleanup and Phase 4.1 close |
| [`archive/README.md`](archive/README.md) | historical docs index |
| [`modules/README.md`](modules/README.md) | platform module map + legacy M1–M6 mapping |
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
