# Group Meeting · 2026-11-04

> Deck source for PPT Master.
> One page = one clear message.
> Every page has English slide copy, Chinese translation, and a diagram brief.

---

# Slide 1 — Title

## English

- Two-Layer Agent Architecture
- Workflow of Nodes + Generic Kernel
- Demo, Data Quality, Results, Next Steps

## 中文翻译

- 双层 Agent 架构
- 多 Node 组成的 Workflow + 通用 Kernel
- Demo、数据质量、结果、下一步

## Diagram Brief

Title slide. Large title on the left, a simple two-layer stack on the right: “Workflow” above “Kernel”.

---

# Slide 2 — Two-Layer Agent Architecture

## English

- Workflow is a fixed chain of five Nodes.
- Each Node calls the Kernel with a Node contract.
- Kernel is one generic agent; it knows no report or paper concepts.

## 中文翻译

- Workflow 是由五个 Node 组成的固定阶段链。
- 每个 Node 通过 Node 契约调用 Kernel。
- Kernel 是一个通用 Agent，不知道 report 或 paper 这些领域概念。

## Diagram Brief

Draw a horizontal Workflow bar with five boxes: Source, Evidence, Plan, Write, Finalize. Each box has a downward arrow to a shared “Kernel” box. The Kernel box contains: Goal, Tool, Observation, Memory, Checkpoint, Budget. Put “Tools” and “Verifier” beside the Kernel as edge attachments.

---

# Slide 3 — Kernel Loop

## English

- Goal + history → LLM decision.
- Tool call → observation → state update.
- Final → schema check → verifier → audit.

## 中文翻译

- 目标 + 历史 → LLM 决策。
- 工具调用 → 观察结果 → 状态更新。
- 最终输出 → schema 检查 → verifier 验收 → audit 审计。

## Diagram Brief

Draw a loop: Goal → Prompt/History → LLM Decision → Tool Call → Observation → State/Checkpoint → back to Prompt. Add two exits: “Final Output” to Schema → Verifier → Audit, and “Failure” to Repair / Max Steps. Show Budget and Context Compaction as side controls.

---

# Slide 4 — Generic Node Flow and Data Contracts

## English

- Each Node receives JSON artifacts and returns JSON artifacts.
- Generic flow: plan → act → verify → checkpoint → commit.
- Final stage adds audit and archive; artifacts stay on disk.

### Node contract (English, on slide)

```text
NodeSpec {
  goal, inputs, toolset, output_schema, verifier, budget
}
```

### Current artifact formats (English, on slide)

| Node | Main input | Main output |
|---|---|---|
| `source.collect` | request: root, query, limit, out_dir | source.json: papers, count, limit |
| `evidence.extract` | source_path, out_dir | evidence.json: claims, papers, target_papers |
| `report.plan` | evidence_path, out_dir | plan.json: sections, coverage |
| `report.write` | plan_path, evidence_path, out_dir | draft.json: sections, word_count, citation_coverage |
| `report.audit_finalize` | draft_path, evidence_path, out_dir | report.json: quality, audit, content_sha |

## 中文翻译

- 每个 Node 接收 JSON artifact，并返回 JSON artifact。
- 通用流程：计划 → 执行 → 验证 → checkpoint → commit。
- 最后阶段增加审计和归档；中间产物保存在磁盘。

| Node | 主要输入 | 主要输出 |
|---|---|---|
| `source.collect` | request：root、query、limit、out_dir | source.json：papers、count、limit |
| `evidence.extract` | source_path、out_dir | evidence.json：claims、papers、target_papers |
| `report.plan` | evidence_path、out_dir | plan.json：sections、coverage |
| `report.write` | plan_path、evidence_path、out_dir | draft.json：sections、word_count、citation_coverage |
| `report.audit_finalize` | draft_path、evidence_path、out_dir | report.json：quality、audit、content_sha |

## Diagram Brief

Draw one Node envelope with input JSON on the left and output JSON on the right. Inside the envelope: Plan → Act → Verify → Checkpoint → Commit. Above it, show the six NodeSpec fields. Below, show the artifact chain: request.json → source.json → evidence.json → plan.json → draft.json → report.json. Add “audit / archive” only at the final stage.

---

# Slide 5 — Report Workflow: Nodes and Tools

## English

- Source: local corpus or online download.
- Evidence: exact quotes and claim extraction.
- Plan: section outline.
- Write: section loop.
- Finalize: quality, audit, persist.

## 中文翻译

- Source：本地 corpus 或在线下载。
- Evidence：抽取 exact quote 和 claim。
- Plan：生成 section 大纲。
- Write：逐 section 写作。
- Finalize：质量门禁、审计、持久化。

### Node details (English, on slide)

| Node | Role | Main tools |
|---|---|---|
| `source.collect` | Build the paper corpus | `source.collect`, `source.collect_online`, `source.search`, `corpus.stats` |
| `evidence.extract` | Extract grounded claims | `evidence.extract`, `claims.extract`, `quote.check` |
| `report.plan` | Plan sections and coverage | `report.plan_v2`, `context.inspect` |
| `report.write` | Write section by section | `report.section_status`, `report.write_next_section`, `report.assemble_v2` |
| `report.audit_finalize` | Quality, audit, persist | `report.finalize_v2`, `report.quality.check`, `verify.code` |

## 中文翻译

| Node | 作用 | 主要工具 |
|---|---|---|
| `source.collect` | 构建论文 corpus | `source.collect`、`source.collect_online`、`source.search`、`corpus.stats` |
| `evidence.extract` | 抽取有出处的 claim | `evidence.extract`、`claims.extract`、`quote.check` |
| `report.plan` | 规划 section 和覆盖范围 | `report.plan_v2`、`context.inspect` |
| `report.write` | 逐 section 写作 | `report.section_status`、`report.write_next_section`、`report.assemble_v2` |
| `report.audit_finalize` | 质量门禁、审计、持久化 | `report.finalize_v2`、`report.quality.check`、`verify.code` |

## Diagram Brief

Draw five vertical columns. Top: Node name. Middle: role. Bottom: 2–3 tool chips. Connect columns with arrows. Under the row, show artifacts: source.json → evidence.json → plan.json → draft.json → report.json.

---

# Slide 6 — Data Sources: Local and Online

## English

- Local: `papers.jsonl` + fulltext files; no download.
- Online: OpenAlex search + PDF/HTML download; skip papers without fulltext.
- Current problems: broad queries, empty metadata, missing fulltext, unstable quality.
- Future: rank candidates by relevance and popularity.

## 中文翻译

- 本地：读取 `papers.jsonl` 和 fulltext 文件，不重新下载。
- 在线：OpenAlex 检索 + PDF/HTML 下载；拿不到全文就跳过。
- 当前问题：query 太泛、元数据为空、fulltext 缺失、质量不稳定。
- 未来：按相关性和热度排序候选论文。

## Diagram Brief

Draw two source branches. Left: Local Corpus → papers.jsonl + fulltext. Right: Online Search → OpenAlex → PDF/HTML → Fulltext Filter → Skip / Keep. Merge both into “source.json”. Add a warning box: “empty metadata / paywall / parse failure”. Add a future arrow: “rank by relevance + citations / recency”.

---

# Slide 7 — 100-Paper Test Result

## English

- 100 papers, 98 fulltext, 196 claims, 23 sections.
- Citation coverage 1.0; quality gate passed; audit accepted.
- 20-paper demo: 20 fulltext, 80 claims, 7 sections.

## 中文翻译

- 100 篇论文，98 篇有全文，196 条 claim，23 个 section。
- 引用覆盖率 1.0；质量门禁通过；audit 接受。
- 20 篇 demo：20 篇全文，80 条 claim，7 个 section。

## Diagram Brief

Use a metrics dashboard. Four big numbers: 100 / 98 / 196 / 23. Below: two green badges: “citation coverage 1.0” and “quality passed”. Add a small comparison card for the 20-paper demo.

---

# Slide 8 — What Is Completed

## English

- Generic Kernel: loop, tools, checkpoint, budget, repair.
- Specialized Workflow: five report Nodes.
- Node contract, toolsets, verifiers, quality gate.
- API, CLI, live SSE, resume, section retry.

## 中文翻译

- 通用 Kernel：循环、工具、checkpoint、预算、修复。
- 特制 Workflow：五个 report Node。
- Node 契约、toolset、verifier、质量门禁。
- API、CLI、SSE 实时更新、resume、section retry。

## Diagram Brief

Draw a checklist board with four sections: Kernel, Workflow, Contracts, Interfaces. Put green checks next to each item. Add a small line: “128 tests / Ruff / frontend build / L3 gate”.

---

# Slide 9 — What Is Not Complete

## English

- Article acquisition is still the weakest part.
- Fulltext coverage, empty metadata, and retrieval quality need work.
- No evidence rollback yet.
- RAG, Qdrant, and Kuzu are still deferred.

## 中文翻译

- 文章获取仍是最薄弱的部分。
- fulltext 覆盖率、空元数据、检索质量都需要改进。
- 还没有 evidence 回退机制。
- RAG、Qdrant、Kuzu 仍然暂缓。

## Diagram Brief

Draw a gap map. Left: “Done” — Kernel, Workflow, UI. Right: “Gaps” — Retrieval, Fulltext, Ranking, Evidence repair, RAG / 3DB. Use red/orange for gaps, green for done.

---

# Slide 10 — Suggested Additions and Next Steps

## English

- Add LLM query planning: generate, run, and merge multiple queries.
- Rank candidates by relevance, citations, and recency.
- Build retrieval evaluation: precision, recall, fulltext yield.
- Ask the advisor: which report sections and quality bar matter most?

## 中文翻译

- 增加 LLM query planning：生成、并行执行、合并多个 query。
- 按相关性、引用量、时效性排序候选论文。
- 建立检索评估：precision、recall、fulltext yield。
- 问导师：哪些 report section 和 quality bar 最重要？

## Diagram Brief

Draw a four-step roadmap: Query Planner → Parallel Search → Rank & Dedupe → Fulltext Filter. On the right, add an “Advisor questions” card with three items: report sections, quality bar, retrieval priority.
