# PPT Master 提示词 — 组会 PPT（Module & Framework Selection）

> 用法：把下面 `===== PROMPT =====` 之间的内容整体复制给模型（或在 DSH 里直接说
> "按 docs/ppt/ppt-master-prompt-group-meeting.md 生成"）。第一轮只出 Slide 1–5 供检查，
> 通过后再用同一套设定续完全部 15 页。
>
> 源文件：`docs/ppt/framework-selection-brief.md`（分页 deck brief，每 `## Slide N` = 一页）
> 支撑文件：`docs/project/framework-selection.md`、`docs/design/architecture-overview.md`、
> `docs/design/challenges-and-self-healing.md`、`docs/implementation/evaluation-plan.md`

===== PROMPT =====

Use the ppt-master skill to build a group-meeting deck.

**Task** — English presentation deck for a supervisor + research group, reviewing module-level
framework selection for the *Intelligent Multi-Agent Literature Research Assistant* (EE5003 MSc
project, NUS). 15 slides, 15–20 min talk. This round: author and export **Slides 1–5 only** as a
style-and-layout sample for review; do not author Slides 6–15 yet.

**Route** — Quick generate (one pass, no confirmation stops). Source is a closed corpus; do not
run topic research.

**Source of truth** — `docs/ppt/framework-selection-brief.md` is the page-by-page content authority:
treat each `## Slide N` block as exactly one slide; keep its title, key message, and content
points; `Visual` and `Speaker note` lines are production hints, not slide copy. Use
`docs/design/architecture-overview.md` and `docs/project/framework-selection.md` only to disambiguate wording.
Never invent facts, numbers, or technology names beyond these files.

**Roster (this round, in order)**
1. Title — deck title, subtitle “Module & Framework Selection — Context & Harness Engineering”,
   meta line, and a bottom tagline strip: Weekly runs · Paper relations · Three interfaces · Dual engine · Built-in evaluation.
2. What the System Must Do — key message plus a 2×3 grid of six requirement cards, one short
   noun phrase each: weekly autonomous runs; self-correction; paper relations & author activity;
   three interfaces; dual engine; built-in evaluation (+ domain line).
3. End-to-End Architecture — one layered architecture diagram, seven layers top→bottom
   (Interfaces / Application services / Orchestration / Context engineering / Model layer /
   Domain services / Storage & sources), a left-to-right weekly-run flow, and one vertical
   cross-cutting “event log” spine called out as the single source of truth for replay, evaluation, audit.
4. Module Map — Final Selections — a designed 10-row comparison table (#, Module, Final selection)
   as the visual centrepiece; visibly highlight the two framework-first changes (rows 2 and 10).
5. Module 1 — Orchestration & Multi-Agent — chosen banner “LangGraph”, a three-option comparison
   (LangGraph chosen / AutoGen / CrewAI) with pros and why-not, plus a mini pipeline graph
   (retrieval → graph build → analysis → report) showing a feedback edge and SQLite checkpointing.

**Presentation logic** — answer-first: every slide's title carries its message; body copy is
evidence. One idea per slide. Comparisons and parallels must be *visual*: tables with aligned
columns and semantic chips, layered/parallel diagrams for architecture, pipeline graph for flow.
No paragraphs longer than two lines. No code, no long sentences, no bullet walls.

**Density** — moderate: Slide 1 breathing; Slides 2–3 balanced; Slides 4–5 dense but calm
(table rows are the density). Keep ≥ 40 px outer margin and clear whitespace between groups.

**Style** — modern technical-review minimalism (my choice):
- Canvas 16:9, `1280×720`; flat pages (free design, no template workspace).
- Palette: background `#FFFFFF`, surface `#F8FAFC`, hairline `#E2E8F0`, ink `#0F172A`,
  muted `#64748B`, accent `#2563EB`, accent-soft `#DBEAFE`, neutral chip `#F1F5F9`.
- Chosen/adopted = filled accent chip; alternative = neutral outline chip; rejected/deferred = muted gray chip.
- Typography: Arial for text, Consolas only for tiny technical tags. Roles: title 30, lede 18,
  body 17, table 14, annotation 12, cover title 54. Never below 12 px.
- Chrome: thin accent tick + slide title top-left, hairline rule, deck short-title bottom-left,
  page number bottom-right (`03 / 15`). Consistent on every page.
- Motifs: 1 px hairlines, left accent ticks, aligned 3-column grids, small geometric icons drawn
  as vectors (no photos, no AI images, no emoji).

**Language** — English only, including slide titles, chips, table cells, and footers. Keep
technology names exactly as in the source (LangGraph, LiteLLM, Kuzu, Qdrant, Ollama, vLLM,
DeepEval, APScheduler, FastAPI, PyMuPDF, OpenAlex, arXiv).

**Output** — export the sample to `exports/` as a native editable PPTX (all five slides), no
speaker notes this round. After export, report: the deck file path, the resolved style/palette,
which charts/diagrams were used on which slide, and anything you simplified for the sample.

===== END PROMPT =====

## 第二轮（样例通过后）

把上面的 **Roster** 换成 `docs/ppt/framework-selection-brief.md` 的 Slide 6–15，并追加一句：

```
Continue the same deck, same style system and chrome. Keep Slides 1–5 unchanged; author
Slides 6–15 from the brief (module comparisons with option tables, challenges matrix,
self-correction detectors table, evaluation plan, roadmap P1–P6 + decisions list).
Export the complete 15-slide PPTX and report the final path.
```

## 检查要点（你验收样例时看这些）

- 每页是否"标题即结论"，一眼能读出这页在说什么
- 对比是否可视化（表格对齐、chosen/alternative/rejected 有语义色块），而不是文字堆
- 架构图是否一眼看懂分层与流向，event log 是否被强调为贯穿主线
- 10 行模块表是否清晰可读、两处 framework-first 变更是否被高亮
- 版面留白、字号、页脚/页码是否统一；英文是否有拼写或术语不一致
