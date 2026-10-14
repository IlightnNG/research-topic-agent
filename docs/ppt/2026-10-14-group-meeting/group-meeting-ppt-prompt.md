# PPT Master 提示词 — 组会汇报（Phase 0 进展）

> 用法：把 `===== PROMPT =====` 之间的内容整体复制给模型（或在 DSH 里直接说
> "按 docs/ppt/2026-10-14-group-meeting/group-meeting-ppt-prompt.md 生成"）。
> **建议分两轮**：第一轮只出 **Slide 1–4** 检查风格与版式，通过后同一套设定续完剩余页。
>
> **语言规则**：标题与正文 **英文为主**；中文只作为**辅**出现在四处——
> ①每页标题下方**一行灰色中文注解**（≤20 字）；②术语**首次出现时**的中文括注；
> ③**问题页（8–13）方法行**末尾的 ≤8 字机制括注；④**验证页（14–21）**四个块标题下与每条公式下的中文注解。
> **表格单元格、图表标签、chip、公式内部一律英文。**
>
> **本版重点**：每页内容**详实**，但**每条内容都带重要度层级 `[H]/[1]/[2]/[3]/[F]`**——
> ppt-master 按层级决定字号、颜色、位置与取舍（`[H]` 最大最亮、`[3]` 最淡且最先被裁）。
> **问题页只讲机制与办法（不含测量数字），验证页讲实现办法 + 公式 + 测试方法 + 实测结果。**
> **字号硬底线：全 deck 任何元素 ≥ 19 px = 14.25 pt。**
>
> **结构（21 页）**：开场 2 页 → 模块一 选型 4 页 → **周更状态图 1 页** → 模块二 代表性问题 6 页
> （**一页一个问题**）→ 模块三 可行性验证 8 页（**一页一个验证**）。
> **不含**静默错误页与决策门页（决策门另出单页文档，口头汇报）。
>
> **内容权威**：`docs/ppt/2026-10-14-group-meeting/group-meeting-outline.md`（思路底稿，中文，供你核对口径）
> 与 `docs/ppt/2026-10-14-group-meeting/phase0-decision-gate.md`（数字）。**不得引入新数字。**

===== PROMPT =====

Use the ppt-master skill to build a group-meeting progress deck.

**Task** — Progress-report deck for the *Intelligent Multi-Agent Literature Research Assistant*
(EE5003 MSc project, NUS). **21 slides.** Narrative: opening → (1) selection review → node-design
bridge → (2) six hard problems, one per slide → (3) eight feasibility verifications, one per slide.
This round: author and export **Slides 1–4 only** as a style-and-layout sample.

**Route** — Quick generate (one pass, no confirmation stops). Closed corpus: **no topic research, no
external fetching.**

**Source of truth** — `docs/ppt/2026-10-14-group-meeting/group-meeting-outline.md` is the content
authority; `docs/ppt/2026-10-14-group-meeting/phase0-decision-gate.md` supplies the numbers.
**Never invent numbers, metrics or technology names.**

## Language — English primary, Chinese secondary (v3, module-aware)

- English carries everything: titles, lede, body, table headers and cells, chips, axis labels, footers.
- Chinese is allowed in **exactly these four places**, and nowhere else:
  1. **Title gloss** — one muted Chinese line directly under each slide title (≤ 20 characters, `#64748B`).
  2. **Term parenthetical** — at a term's **first appearance only**: `Scope Anchor（范围锚点）`,
     `stage contracts（阶段契约）`, `recovery packet（恢复包）`, `escalation ladder（升级阶梯）`.
     A term is glossed once in the whole deck; later occurrences carry no parenthetical.
  3. **Problem pages (8–13), method lines** — a `[2]` method line may end with **one** short Chinese
     parenthesis (≤ 8 characters) naming the mechanism it implements, e.g. `… injected into every node's
     system slot（版本化注入）`. At most one parenthesis per line, never two lines in a row.
  4. **Verification pages (14–21), blocks and formulas** — one Chinese line (≤ 14 characters) under each
     of the four block headers, and one Chinese line (≤ 12 characters) directly **under** a formula block
     saying what it computes, e.g. `block = (min_on + max_off) / 2` → `阈值下界取分布间隙中点`.
- **Never put Chinese inside a table, chart label, chip or formula**, and never translate the technology
  names listed below.
- Cover is bilingual: English title, English subtitle, then the Chinese subtitle line.
- Never translate: LangGraph / LiteLLM / OpenRouter / AutoGen / OpenAI Agents SDK / Kuzu / Qdrant /
  SQLite / DeepEval / FastAPI / Vue3 / OpenAlex / arXiv / DeepSeek / LangChain / LangSmith / MCP /
  grounding / citation / checkpoint / novelty.
- CJK-safe sans for every Chinese line; Chinese must never render as boxes.

## Importance tiers (every content line in the Roster is tagged — respect the tags)

| Tag | Meaning | How to render | Quota per slide |
|---|---|---|---|
| **`[H]`** | **Hero — the one claim the audience must remember, in words** | one self-explanatory sentence (≤ 18 words, 26–28 px, ink) on an accent-soft `#DBEAFE` card, with the supporting number(s) on a 19 px line directly beneath **and a plain-language meaning for each number**; must be understandable with nothing else on the slide | **exactly 1 — or 0 when the `[1]`/`[2]` lines already carry the message** |
| **`[1]`** | Primary — the slide's argument spine | L2 block header 24 px in accent + one 21 px line under it, ink `#0F172A` | 1–4 (table-centric slides use 1: the table itself) |
| **`[2]`** | Secondary — supporting detail that makes the argument credible | 19 px, muted `#64748B`, grouped under its `[1]` | ≤ 8 (problem pages carry 5–7 method lines) |
| **`[3]`** | Footnote — caveats, boundaries, cross-references | 19 px, muted `#94A3B8`, at the block's foot or in a single bottom note line | ≤ 6 |
| **`[F]`** | **Formula — a computation shown as plain text** (verification pages 14–21 only) | one line at 19–21 px, ink, Consolas allowed; **exempt from the word budget**; each `[F]` may be followed by one Chinese gloss line (≤ 12 characters) saying what it computes | 1–5 per slide |

**Type floor (hard)** — the canvas is `1280×720`, so `1 px = 0.75 pt` and **nothing may render below
19 px = 14.25 pt** — not a footnote, not a table cell, not a chart label. Because everything shares that
floor, hierarchy below the hero is carried by colour, weight and position rather than by shrinking type
(`[2]` `#64748B`, `[3]` `#94A3B8`, chips and hairlines doing the rest).

**Tag rules by module**
- **Problem pages (8–13)** = mechanism only. **No measured numbers, no `[F]`, no "how we verified" line**
  — those belong to Module 3. Hero is the mechanism claim (words only). The sole exception is a
  **diagram hero whose numerals are design constants, not measurements** — e.g. slide 10's ladder rungs
  at 80% and 100% of the configured budget.
- **Verification pages (14–21)** = evidence only. Four fixed blocks `How we measured · Formulas ·
  Results · Impact`; **no `Why` block** (motivation was already carried by the matching problem page).
  Hero is the verdict with its numbers.

**Drop order when space is tight** — `[3]` first, then trim `[2]`; never drop `[H]`, never drop a `[1]`,
never drop a `[F]` that a verification page needs to be defensible, never drop the takeaway strip.
`[3]` items are the deliberate overflow buffer: keeping them small and grey is correct even when they
all fit.

## Hero writing rules (v2 — a hero must explain itself)

A bare number pair with a two-word label is **not** a hero: the audience cannot tell what it means, why
it is good, or what it proves. Every `[H]` therefore carries three parts, inside one accent-soft card:

1. **Claim** — one clause, ≤ 18 words, plain language, no numbers: what is true and why it matters
   (26–28 px, ink `#0F172A`).
2. **Evidence** — the number(s) that back the claim, each with a short meaning in the same line
   (19 px, muted `#64748B`).
3. **Meaning** — if a number is not self-evident (a threshold, a rate, a percentile), say in words what
   it measures; never leave a bare `x / y` unexplained.

Rules:

- Never let a bare `x / y`, a single number, or a two-word label be the whole hero. If the fact cannot
  be explained in words, **delete the card** and fold the fact into the `[2]`/`[3]` lines instead.
- A hero may also be a **diagram** (node chain, ladder, layered stack) when the mechanism is the point —
  diagrams explain themselves and stay.
- On **problem pages (8–13)** the hero states the **mechanism** and carries **no measured numbers**;
  the numbers belong to Module 3 and must not leak into these pages.
- On **verification pages (14–21)** the hero states the **verdict**, with its numbers and their meaning.
- The hero never carries a caveat or a `[3]`-level note; those stay small and grey at the block foot.
- Worked examples: Slide 8 = "Scope Anchor（范围锚点）and stage contracts keep a run on topic" (mechanism,
  no numbers) · Slide 20 = "Every injected fault was caught, with no false alarms" + "detection 1.00
  (5 fault families × 3 runs) · false positives 0/3" (verdict + numbers).

**Body copy (per module)** — comparison slides stay light (~60–90 English words). **Problem pages
(8–13)** may carry more: 5–7 `[2]` method lines, each ≤ 14 words, describing *how the mechanism works*,
plus a `[3]` boundary line and a cross-reference line — never how it was measured. **Verification pages
(14–21)** may carry up to ~140 words across their four blocks; `[F]` formula lines and their Chinese
glosses are **exempt** from the word count. The **tier quotas are the binding constraint**: if a slide
overflows, delete `[3]` first, then trim `[2]` wording — never shrink the hero, never drop a `[1]` or an
`[F]` that makes a verification page defensible. Lines are **fragments, not sentences**.

**Tables** — ≤ 6 rows × 4 columns, ≤ 6 words per cell; exceptions: Slide 3 (10 rows, ≤ 3 words/cell) and
Slide 4 (8 rows, ≤ 4 words/cell). Table header row is `[1]` weight; cells are `[2]`.

**Bottom takeaway strip (L5) on every slide except the cover** — one line ≤ 12 words, `#F1F5F9`
background with an accent left tick; this is the answer-first device and must appear verbatim.

## Hierarchy (identical geometry on every slide)

| Level | Role | Style |
|---|---|---|
| L1 | Slide title = the message | 40 px, ink `#0F172A`, one clause |
| L1.5 | Chinese gloss | 19 px, muted, directly under the title |
| L2 | 2–4 `[1]` block headers | 24 px, accent, short noun phrases |
| L3 | `[1]`/`[2]` lines under each header | 21 px then 19 px, ink then muted |
| **L4** | **`[H]` hero — a claim, not a number** | self-explanatory claim 26–28 px (ink) + evidence line 19 px (muted) on an accent-soft card |
| L4.5 | `[3]` footnotes | 19 px, muted `#94A3B8`, bottom of their block |
| L5 | Bottom takeaway strip | 19 px, muted background, accent tick |
| — | `[F]` formulas (verification pages) | 19–21 px, ink, Consolas; Chinese gloss line 19 px beneath |

- **Nothing below 19 px = 14.25 pt.** The deck is read in a meeting room and from a shared screen; a
  smaller footnote is not contributing, it is decoration.
- Modules reuse fixed layouts so the audience learns the shape once:
  **Problem pages (8–13)** = full-width mechanism hero card (`y 172`–`248`), then a `Problem` band, then a
  **full-width one-line `Methods` list** (5–7 levers, adaptive 26–34 px pitch, no measured numbers), then
  one muted design footnote and the `→ evidence: <slide>` cross-reference at the block foot;
  **Verification pages (14–21)** = full-width verdict hero card, then two columns —
  **left `x 64–624`: `How we measured` (≤3 lines) and `Results` (≤3 lines) plus a one-line caveat;
  right `x 644–1216`: `Formulas` (1–5 cells, each formula line + optional indented substitution + Chinese
  gloss)** — closing on a single-line `Impact` strip at `y 618`; no `Why` block; each of the four block
  headers carries its ≤14-char Chinese gloss on the line beneath it.
- Never shrink the type to make content fit: shorten the clause, or move its detail into the speaker note.
  The full mechanism sentence and the full caveat belong to the notes, not to a smaller font.
- Problem pages are **mechanism-only**: if a measured number wants to appear here, it belongs on the
  matching verification page instead. The recurring detail pages are 8→20/21, 9→20, 10→18/20, 11→20/21,
  12→18, 13→21.
- Method pitch is adaptive (26–34 px) so the list fills the page whatever the lever count; the footnote
  sits at `y 580` and the `→ evidence` line at `y 604`, on every problem page.
- Where a slide has both a hero and a table, the hero sits in the **top-right or centre-right** and the
  table keeps the left; never let them compete for the same optical weight.

## Roster (21 slides)

**How to read this Roster** — every entry is already at slide scale and tagged. Place only what is
listed; never expand an entry into sentences and never add facts. The last line of each entry is the
takeaway strip and must appear verbatim. On verification pages (14–21) the Chinese block gloss is written
after the block header separated by `—` (**render it as its own small line directly under that header**),
and each `[F]` formula carries its Chinese gloss after `→` (**render it on the line directly beneath the
formula**). On problem pages (8–13) the trailing `→ evidence: <slide>` line is the block-foot
cross-reference, not a `How we verify` block.

**Rendered-form contract (v4, what actually ships)** — the roster entry is the content authority; the
slide shows its leading clause at the type floor, and **the entry's full sentence becomes that slide's
speaker note** (`notes/total.md`). Concretely:
- a problem-page method entry renders as **one line** (bold mechanism name + muted tail, ≤ 1152 px at
  19 px) — never wrapped into a second line, never given a smaller size;
- a verification-page `[F]` renders as one or two lines inside the right-hand Formulas column: the
  symbolic line, then (when the arithmetic matters) an indented muted substitution line showing the
  numbers, then the ≤12-char Chinese gloss line;
- the caveat renders as **one** muted line under Results; the long form of every caveat and of every
  mechanism explanation lives in the notes, which is why notes are enabled for this deck.
- Verified on the v4 export: 21 slides, minimum run **14.2 pt** in the PPTX, notes on 21/21 slides.

1. **Cover** — Title "Intelligent Multi-Agent Literature Research Assistant"; Subtitle "Phase 0 Progress
   Report · Context & Harness Engineering"; Gloss "智能多智能体文献研究助手 · Phase 0 进展汇报";
   nav strip `① Selection · ② Hard problems · ③ Evidence`; meta "NUS EE5003 · 2026-10-13".
   (No hero, no takeaway strip on the cover.)
2. **Conclusion first** — Title "Viable, verified, ready for Phase 1"; Gloss "结论先行：选型可行、闭环跑通".
   - `[H]` **`4.42 ms` · `1.00 / 0` · `$0.006`** — graph 2-hop p95 · guard detection / false positives · cost per run
   - `[1]` Sources — whitelist-first retrieval over target venues
     - `[2]` whitelist recall **386 papers / 3 y** (≈129/y, lower bound); arXiv-in-OpenAlex **91.7%**
   - `[1]` Closed loop — a report that can be audited
     - `[2]` **100%** of claims citable; report 8.9k–10.8k characters; **16–23** claims per run
   - `[1]` Self-correction — guards proven by injection
     - `[2]` 5 fault families × 3 runs: detection **1.00**, false positives **0**
   - `[3]` Three stores hold at 5k papers (64.9 MB) · resume granularity = node boundary · checkpoint 4 KB per step
   - Takeaway: "Phase 0 targets met — ready to start Phase 1".
3. **Module map** — Title "Ten modules, ten decisions"; Gloss "模块选型总表：十行定稿".
   - `[H]` the 10-row table itself (`#` · `Module` · `Choice`), rows 1–2 carrying filled accent chips
   - `[1]` Framework-first rows — **1 Orchestration: LangGraph** · **2 Gateway: LiteLLM (in-process SDK)**
   - `[2]` Rows 3–10 — local inference (deferred, cloud-only this round) · graph store Kuzu · vector store
     Qdrant (local) · sources & parsing OpenAlex + arXiv with self-built parsing · scheduling APScheduler ·
     web backend FastAPI · frontend Vue3 + Vite + ECharts · evaluation DeepEval + custom event metrics
   - `[3]` Every choice traces to a Phase 0 measurement — see slides 14–21
   - Takeaway: "Framework-first where it matters".
4. **LangChain vs this project** — Title "Mostly a wrapper layer, not an engine"; Gloss
   "LangChain 各模块 vs 本项目选型".
   - `[H]` the `What it is` column, tinted to read "wrapper over a third-party library"
   - `[1]` One 8-row table, columns `Module` · `LangChain part` · `What it is` · `Ours` (cells ≤ 4 words):
     Orchestration — LangGraph (its own engine) — engine — LangGraph adopted; Gateway — provider model
     classes — vendor-SDK wrapper — LiteLLM; Sources & parsing — community loaders — pypdf/Unstructured
     wrapper — direct clients + own chunker; Retrieval — retrievers — hidden pipeline — explicit filter,
     dedup, novelty; Stores — vectorstore wrappers — trimmed capability — official clients; Memory &
     agents — `langchain-classic` — legacy, superseded — LangGraph checkpoints; Evaluation & tracing —
     LangSmith — SaaS — DeepEval + own event table; Service & tracing — langserve / callbacks — route
     wrapper — own FastAPI + event truth source
   - `[2]` Why ours fits: capability stays at full strength (payload filters, local mode, quantisation) ·
     prompts and tool formats stay visible · no version matrix to maintain
   - `[3]` The v1 migration moved chains, AgentExecutor and memory into `langchain-classic` and made
     LangGraph the orchestration core
   - Takeaway: "Same libraries, one less layer".
5. **Orchestration** — Title "A state machine, not a chat room"; Gloss "编排内核三选一".
   - `[H]` **LangGraph** column (chosen) — filled accent
   - `[1]` 3-column table × 4 rows: control flow · recovery granularity · observability · vendor neutrality
   - `[2]` Built for: product backends embedding LLM flows (chosen) / multi-agent conversation research
     (AutoGen) / shipping agent apps fast (OpenAI Agents SDK, kept for the Chat page)
   - `[3]` Why not the others: AutoGen hides control flow in dialogue turns and was rewritten in v0.4 ·
     OpenAI Agents SDK is OpenAI-first and its guardrails are input/output checks, not stage guards
   - Takeaway: "LangGraph chosen".
6. **Gateway** — Title "A transport layer we can audit"; Gloss "网关三选一".
   - `[H]` **LiteLLM** column (chosen) — in-process SDK
   - `[1]` 3-column table × 3 rows: in-process (no new service) · cost table + retries + health cooldown ·
     third-party hop
   - `[2]` Our thin layer on top: content-addressed cache · truncation detection · budget breaker ·
     every call written as an event (tokens, cost, latency, cache hit)
   - `[2]` Why not self-built (≈300 lines): 100+ provider adapters, price tables and retry policy would
     all become our maintenance burden
   - `[3]` OpenRouter in one line: hosted aggregator giving one key, many models, auto-failover and
     data-policy filters — **not here** because of the data hop, no local engines and hidden failures;
     kept for one-off model benchmarking
   - Takeaway: "LiteLLM chosen, in-process".
7. **Weekly-run graph** — Title "Ten nodes, guards between them"; Gloss "周更状态图：节点与守卫".
   - `[H]` the node chain itself (diagram, never prose)
   - `[1]` Ten nodes, two rows of five, each `id + name + role`: S0 `scope_check` validate scope ·
     S1 `plan` subtasks · S2 `retrieve` evidence cards · S3 `ingest_parse` parse + chunk ·
     S4 `map_update` idempotent writes · S5 `novelty` diff vs last week · S6 `analyze` cited findings ·
     S7 `draft` report + claims · S8 `critique` cross-vendor review · S9 `finalize` persist report + metrics
   - `[1]` Five guard diamonds on the chain: G1 drift (S0–S1) · G2 out-of-scope (S2) ·
     G4 loop + G5 stagnation (any node) · G7 citation resolvable (S6–S7) · G8 budget (any node)
   - `[2]` Four labelled back-arrows: scope fail → S1 · stagnation → S1 replan · critique below
     threshold → S7 rewrite · budget exceeded → S9 finalize-or-abort
   - `[2]` Spine across all nodes: "checkpoint per node — resume = node boundary"; corner ladder
     `retry → degrade → replan → abort (annotate)`
   - `[3]` The full E1–E13 edge table lives in the design doc; this page shows only the four most
     instructive edges
   - Takeaway: "Guards sit between the nodes".
8. **Problem 1 — anti-drift** — Title "How we keep a weekly run on topic"; Gloss "如何防止 agent 走偏".
   - `[H]` **A versioned `Scope Anchor` with a calibrated boundary** — scope is a stored object the
     harness can check, not an instruction the model is asked to respect
   - `[1]` Problem — early drift is amplified downstream, and "zero drift" cannot be promised, so
     detection must be bounded, detectable, reversible and measurable
   - `[1]` Methods — seven levers, all deterministic
     - `[2]` **Scope Anchor（范围锚点）** — one object holding the statement, the in-scope boundaries and
       the counter-examples, version-stamped and injected into every node's system slot; the retrieval
       scorer and the drift guard read the *same* object, so scope can never fork into two definitions
     - `[2]` **Seed-corpus centroid（种子语料质心）** — the anchor is represented as the mean embedding of
       the accepted seed papers, which turns "is this still on topic" into a cosine distance instead of a
       judgement call by the model
     - `[2]` **Stage contracts（阶段契约）** — per-stage input and output schema with validators; a stage
       cannot be skipped and cannot hand an unvalidated shape to the next node
     - `[2]` **Role split + cross-vendor critic（角色分离）** — each agent sees only what it needs, and
       the critic may read and score but never write
     - `[2]` **Evidence-first（证据优先）** — every claim carries a citation that must resolve inside the
       corpus snapshot
     - `[2]` **Hard limits in code（代码内硬约束）** — source whitelist, time window and dedup
       fingerprints are enforced in code, never requested in the prompt
     - `[2]` **Cross-week anchoring（跨周锚定）** — per-topic track state is persisted and diffed against
       the previous week, so slow drift shows up as a trend instead of one bad run
   - `[3]` Design consequence: because scope is one versioned object, a new topic costs one recalibration,
     and every old run stays readable against the anchor version it ran on
   - `[3]` `→ evidence: slide 20` — the two calibrated thresholds, and the counter-example that forced the
     representation change
   - Takeaway: "Detected, reversible, measured".
9. **Problem 2 — loops and stagnation** — Title "How it notices it is going in circles"; Gloss
   "死循环与停滞：检出与处置".
   - `[H]` **Cheap repetition signatures plus a bounded ladder** — a loop is replanned once, then stopped
     by the state machine rather than by a wall-clock timeout
   - `[1]` Problem — the same query re-issued, zero new facts, cost rising with no output, and nobody
     watching an unattended run
   - `[1]` Methods — five detectors, two exit rules
     - `[2]` **Signature window（签名窗口）** — tool name plus a normalised hash of its arguments, kept
       over a sliding window k=5 and firing at repeat ≥ 3; pure comparison, no model call
     - `[2]` **State-hash repetition（状态哈希重复）** — the same state hash reached twice means the
       graph returned to a place it has already paid for
     - `[2]` **Facts delta = 0（事实增量归零）** — a verified-fact set that stops growing detects
       stagnation directly, before it has even started to look like a loop
     - `[2]` **Bounded back-edges（有界回边）** — the state machine permits only a limited number of
       replans per node, counted in state, so re-entry can never be unbounded
     - `[2]` **Escalation ladder（升级阶梯）** — the first hit replans with a changed strategy and a
       recovery packet; a second hit aborts and annotates the report instead of retrying forever
   - `[3]` Design consequence: both detectors read only the event log and the state hash, so policing a
     loop never adds tokens to the run being policed
   - `[3]` `→ evidence: slide 20` — injected repeated-call and zero-progress scenarios, plus the
     normal-run false-alarm count
   - Takeaway: "First replan, then hard stop".
10. **Problem 3 — budget** — Title "How it stops burning money"; Gloss "预算失控：四维看门狗".
    - `[H]` ladder graphic (diagram, never prose) — four meters → degrade early → warn at 80%
      (non-blocking) → stop at 100% (annotate, keep the partial report): the ceiling is enforced by the
      harness, not requested in the prompt
    - `[1]` Problem — an unattended run has no natural cost ceiling, and "let it finish" is the wrong
      default when the meter is the only thing still moving
    - `[1]` Methods — a watchdog with teeth
      - `[2]` **Four meters（四维计量）** — tokens · seconds · cost · steps, re-read after every model and
        tool call, so the number that trips the ladder is always the current one
      - `[2]` **Budget from config（配置注入）** — every ceiling is declared per topic and overridable
        there, so one expensive topic cannot inherit a cheap default
      - `[2]` **Early degradation（提前降级）** — once the trend is visible the run drops to a cheaper
        model tier and shorter retrieval batches *before* the ceiling, not after it
      - `[2]` **Two rungs（两级阈值）** — the warn rung is non-blocking and only marks the event; the stop
        rung halts the graph and annotates the report, because a partial report beats a burnt budget
      - `[2]` **Event per decision（逐决策留痕）** — each reading emits a `metric` event and each verdict a
        `guard_trigger`, so the ladder itself is auditable after the fact
    - `[3]` Related ceilings live in the same config block: per-node timeout and the graph recursion limit
    - `[3]` Design consequence: the ladder `retry → degrade → replan → abort` is data, not scattered code
      paths — the watchdog chooses the rung, the state machine executes it
    - `[3]` `→ evidence: slide 18` (cost of a checkpoint per super-step) and `slide 20` (the budget
      scenario)
    - Takeaway: "Warn at 80%, stop at 100%".
11. **Problem 4 — hallucination** — Title "No unsupported claim ships"; Gloss "如何控制幻觉与事实性".
    - `[H]` **Factuality is enforced by contract and by resolvable citations** — a claim that cannot be
      traced back into the corpus snapshot never leaves the node
    - `[1]` Problem — long chains invite fabricated numbers and silent contradictions, and "be careful"
      is not a mechanism anyone can test
    - `[1]` Methods — factuality enforced at six points
      - `[2]` **Claim + evidence are one unit（声明与证据同体）** — the schema rejects a claim object that
        carries no citation field, so an unsupported sentence cannot reach the report stage at all
      - `[2]` **Citations must resolve（引用可回查）** — `paper_id` plus snippet must be found in the
        corpus snapshot; a failure is marked unverified and counted into the hallucination rate
      - `[2]` **Contradictions are first-class（矛盾显式保留）** — when sources disagree the report
        presents the disagreement, never a silent average
      - `[2]` **Refusal is legal（允许拒答）** — "insufficient evidence" is an accepted output, provided
        it names what is missing and what would settle the question
      - `[2]` **Numbers carry provenance（数字带出处）** — every quantitative statement comes from a tool
        result, and no source silently wins over another
      - `[2]` **Cross-vendor critique（跨厂商评审）** — a second vendor's model re-reads each claim
        against its cited snippet before finalize, and the critic cannot rewrite the claim
    - `[3]` Design consequence: the resolver runs on the same corpus snapshot the retrieval used, so a
      citation that resolves today still resolves after a re-import
    - `[3]` `→ evidence: slides 20–21` — citation-resolvable rate, grounding, and the metric caveat
    - Takeaway: "Unsupported claims cannot pass".
12. **Problem 5 — context growth** — Title "Keep a long run inside the window"; Gloss
    "长跑上下文膨胀：折叠与分层".
    - `[H]` **State holds `summary + pointers`, and folding is an explicit node** — raw text never enters
      the window, so context size is a design decision instead of a side effect
    - `[1]` Problem — a run spans hours, so state, tool results and retrieval history grow without bound,
      and on-device tiers are tighter still
    - `[1]` Methods — fold explicitly, store pointers
      - `[2]` **Summaries and pointers only（只存摘要与指针）** — state keeps `paper_id` and event ids;
        raw text stays in the filesystem and the stores, and is re-read on demand
      - `[2]` **Budget before every call（调用前算预算）** — the token budget of a model call is computed
        from the state that call will receive, and folding is a node, never an implicit behaviour
      - `[2]` **Folding rules（折叠规则）** — retrieval history becomes structured points plus citations,
        old dialogue becomes a sliding window plus a summary, and long documents never enter whole
      - `[2]` **Three-layer memory（三层记忆）** — topic state / evidence stores / report history, each
        with its own read interface and its own lifetime
      - `[2]` **Fixed injection slots（固定注入槽）** — system (scope + state + policy) / user (current
        task) / tools (result cards carrying citations), so prompt assembly is deterministic
      - `[2]` **Folding is auditable（折叠可审计）** — every fold emits before/after token counts, which
        turns window pressure into a number instead of a mystery
    - `[3]` Status: designed and instrumented, **not yet measured** — Phase 0 data volume is too small to
      stress the window
    - `[3]` `→ evidence: slide 18` — the checkpoint that makes restart cost independent of run length
    - Takeaway: "Fold first, then route".
13. **Problem 6 — validating tool and MCP returns** — Title "How we validate what tools return"; Gloss
    "如何验证工具/MCP 返回的数据是否合法".
    - `[H]` **Six validation layers, and the first four need no LLM** — whatever schema or arithmetic can
      decide is decided without a model call, and critical actions fail closed
    - `[1]` Problem — tool output is untrusted data, and one word, "reasonable", hides four different
      questions: protocol validity, numeric domains, cross-field consistency, semantics
    - `[1]` Methods — a six-layer pipeline, cheapest layer first
      - `[2]` **L0 protocol（协议层）** — JSON-RPC validity, `isError`, output schema, types and enums,
        all checked with Pydantic before a single field is read
      - `[2]` **L1 domain rules（域规则层）** — 0 ≤ ratio ≤ 1 · `cited_by` ≥ 0 · year ≤ current ·
        published ≤ updated · citation resolvable in the local store · unit normalisation · source
        whitelist · freshness · dedup
      - `[2]` **L2 cross-source recompute（跨源重算）** — key numbers recomputed from an independent
        second source (OpenAlex ↔ Crossref ↔ local graph) instead of being trusted once
      - `[2]` **L3 statistical anomaly（统计异常）** — z-score and IQR against the history plus count
        spikes, which catch plausible-looking values that are simply out of family
      - `[2]` **L4 LLM for semantics only（仅语义用 LLM）** — rubric-based, cross-vendor, sampled and
        cached, and reached only after L0–L3 have passed
      - `[2]` **L5 human spot-check（人工抽检）** — calibrates the judge, not the data
      - `[2]` **Fail-closed policy（失败即拒绝）** — a failed layer means no graph write, no evidence-pool
        entry and no report claim; the unsupported path is never the convenient one
    - `[3]` Design consequence: the same validators wrap MCP tool returns and our own node outputs, so one
      failure taxonomy covers the whole graph
    - `[3]` `→ evidence: slide 21` — the injection runs used to check interception and false positives
    - Takeaway: "No LLM until layer four".
14. **Verification 1 — sources (S1)** — Title "Can the whitelist see the venues?"; Gloss
    "验证 1：数据源覆盖度".
    - `[H]` **The whitelist does reach our target venues, and arXiv is indexed there** — whitelist recall
      **386 papers / 3 years** (≈129/yr, a floor) · arXiv-in-OpenAlex **91.7%** · relevance spot-check
      **10/10** · **20/20** requests HTTP 200, p50 1.09 s
    - `[1]` How we measured — 测量方法
      - `[2]` counted whitelist-venue recall over a three-year window by querying the 12 configured
        source ids; matched arXiv preprints to OpenAlex records by DOI; sampled retrieved records and
        scored relevance by hand; probed the polite-pool rate limit with 20 sequential requests,
        recording HTTP status, errors and latency percentiles
    - `[1]` Formulas — 计算公式
      - `[F]` `papers_per_year = N_whitelist / years = 386 / 3 ≈ 129` → 年召回下界
      - `[F]` `coverage = matched_preprints / sampled_preprints = 0.917` → arXiv 命中率
      - `[F]` `p50 = percentile(latency, 50)` → 延迟中位数
    - `[1]` Results — 实测结果
      - `[2]` whitelist **386 papers / 3 years** (≈129 per year, a lower bound); arXiv coverage
        **91.7%**; relevance **10/10**; **20/20** requests HTTP 200 with p50 1.09 s
    - `[1]` Impact — 结论影响
      - `[2]` whitelist filtering must be the primary retrieval channel, with arXiv as a freshness
        supplement rather than a gap-filler
    - `[3]` Caveat: NeurIPS / ICLR / OSDI records are missing from the count, so 386 is a floor
    - Takeaway: "Sources verified".
15. **Verification 2 — retrieval and dedup (S1b)** — Title "Which strategy, how much reference data?";
    Gloss "验证 2：检索 / 去重 / 引用完整率".
    - `[H]` **The whitelist searches a different corpus than broad recall, so both strategies and a
      stronger dedup key are needed** — whitelist↔broad overlap **0.004–0.014** · same-title duplicates
      **19.3–19.8%** · reference completeness **1.5% / 14.3%** against broad **25–27%**
    - `[1]` How we measured — 测量方法
      - `[2]` ran broad, whitelist and query-expansion strategies over the same three-year window (994
        records); compared result sets by title to get overlap; counted same-title duplicate groups;
        cross-checked papers with no references by DOI across all versions; probed incremental cursors
        for stability and page overlap
    - `[1]` Formulas — 计算公式
      - `[F]` `J(A,B) = |A ∩ B| / |A ∪ B|` → 结果集重合度
      - `[F]` `dup_rate = dup_records / records = 101/511, 93/483` → 同标题重复率
      - `[F]` `ref_completeness = papers_with_refs / papers` → 引用完整率
      - `[F]` `new = |E \ W|` → 扩展查询新增数
    - `[1]` Results — 实测结果
      - `[2]` query expansion adds **126/155** papers; references are present in 25–27% of broad records
        against **1.5% / 14.3%** of whitelist records; `from_updated_date` is a **paid feature (429)**
        while `from_publication_date` with a cursor is stable (page-2 overlap 0)
    - `[1]` Impact — 结论影响
      - `[2]` whitelist plus multi-query expansion; a dedup key of DOI + normalised title + year with
        `merged_ids`; reverse `cited_by` edges; publication-date watermark for incremental sync
    - `[3]` The DOI cross-check confirmed the reference gap is a source property, not a version artefact;
      a `2050-02-21` publication date was found, so date sanity filtering is mandatory at ingest
    - Takeaway: "Retrieval plan fixed".
16. **Verification 3 — storage stack (S3)** — Title "Do three stores survive 5k papers?"; Gloss
    "验证 3：存储栈（三库）".
    - `[H]` **The three-store split holds at 5,000 papers and no store swap is needed** — graph 2-hop p95
      **4.42 ms**, author aggregation p95 5.06 ms, SQLite p50 0.07 ms · re-import grew every count by
      **0** · total disk **64.9 MB**
    - `[1]` How we measured — 测量方法
      - `[2]` imported 5,000 real records into SQLite, Kuzu and Qdrant; ran four query classes 30 rounds
        each and read p50/p95 from the timings; re-imported the same batch to test idempotency; deleted
        the indexes and rebuilt them from the truth source; probed concurrent writes, disk footprint and
        edge cases
    - `[1]` Formulas — 计算公式
      - `[F]` `p95 = percentile(latency, 95)` → 95 分位延迟
      - `[F]` `growth = count_after − count_before = 0` → 幂等零增长
      - `[F]` `disk = kuzu + qdrant + sqlite = 12.89 + 49.06 + 2.95 = 64.90 MB` → 磁盘合计
    - `[1]` Results — 实测结果
      - `[2]` all **20,000** edges written through `MATCH+MERGE`; the rebuild reproduced identical
        counts; single-writer semantics confirmed; import times were sqlite 0.22 s, qdrant 26.78 s,
        kuzu 169.46 s
    - `[1]` Impact — 结论影响
      - `[2]` no store swap is needed (Neo4j / Milvus unnecessary); count reconciliation became
        mandatory because edges can be skipped silently; the vector-latency item moves to Phase 1
    - `[3]` Two silent traps found here: a stale Kuzu database inflated author counts (631 vs 957), and
      Kuzu only flushes on `Database.close()`, which produced a 0.0 MB false reading
    - Takeaway: "Storage decided".
17. **Verification 4 — vector latency (S3b)** — Title "Why vector search missed its target"; Gloss
    "验证 4：向量检索延迟归因".
    - `[H]` **The 155 ms is a property of the deployment mode, not a flaw in the architecture** — pure
      math floor **0.65 ms (0.3%)** · Python glue ~26% (49.91 ms without filters) · payload filtering
      **+140 ms (74%)** · local mode has **no ANN**, so it is exact kNN
    - `[1]` How we measured — 测量方法
      - `[2]` read the local-mode implementation (0 occurrences of HNSW, 0 of `np.dot`); then ran an
        attribution probe at 5,000 points / 1,024 dims — numpy brute-force floor, local without filter,
        local with `topic`, with `year`, with both, and with a payload index built — followed by a scale
        curve from 1,250 to 5,000 points, all in one process so only the ratios are relied on
    - `[1]` Formulas — 计算公式
      - `[F]` `share = component / total = 0.65 / 189.32 ≈ 0.3%` → 纯算力占比
      - `[F]` `overhead_filter = t_filtered − t_unfiltered ≈ +140 ms` → 过滤开销
      - `[F]` `slope = Δt / Δpoints = (189.32 − 51.93) / (5000 − 1250) ≈ 0.038 ms/point` → 线性斜率
      - `[F]` `t(20k) ≈ 0.038 ms × 20000 ≈ 0.76 s` → 规模外推
    - `[1]` Results — 实测结果
      - `[2]` local without filters **49.91 ms** p50; payload indexes have **no effect** in local mode;
        `year>=2020` matches all 5,000 points yet still costs +112 ms, so filter cost tracks scanned
        points rather than selectivity; `retrieve` by id 0.02 ms
    - `[1]` Impact — 结论影响
      - `[2]` local mode is exact kNN — higher recall, slower; the deployment mode (accept local / run a
        local server / switch to embedded ANN) is a Phase 1 decision, and the acceptance target has to
        be recalibrated against whichever form is chosen
    - `[3]` The 100 ms target implicitly assumed a production ANN engine, which the embedded mode is not
    - Takeaway: "Not a design flaw".
18. **Verification 5 — crash resume (S4)** — Title "Six scenarios, three hard kills"; Gloss
    "验证 5：断点续跑".
    - `[H]` **Resuming at the node boundary reproduces the run exactly, but passing the full input does
      not** — `invoke(None)` matched the control state field by field · events stayed **1..N** across
      three hard kills · checkpoint **28–37 KB** in total, ≈4 KB per super-step
    - `[1]` How we measured — 测量方法
      - `[2]` ran six scenarios (control, single crash, double crash, input drift, re-trigger, correct
        resume) with deterministic `os._exit(9)` kills, never a simulated exception; compared the final
        state and the event sequence across processes; read checkpoint size from the SQLite checkpoint
        tables
    - `[1]` Formulas — 计算公式
      - `[F]` `resume_ok = (state_resumed == state_control)` → 状态逐字段一致
      - `[F]` `ckpt_per_step = checkpoint_bytes / super_steps ≈ 4 KB` → 单步检查点
      - `[F]` `gaps = N_expected_events − N_observed = 0` → 事件序号无缺口
    - `[1]` Results — 实测结果
      - `[2]` `invoke(None)` reproduces the control state field by field; passing the full input
        **replays from START** (fetch ran 2–3 times); crashed nodes always re-run; input drift and
        re-triggering are **not** blocked by the framework; checkpoint database 28–37 KB
    - `[1]` Impact — 结论影响
      - `[2]` node idempotency became a hard requirement and a resume guard (G15) was added for input
        drift and finished-run re-triggering; the event log can serve as the post-crash truth source
    - `[3]` Events stayed contiguous across three kills, which is what makes the event log usable as
      that truth source
    - Takeaway: "Resume rule book".
19. **Verification 6 — closed loop (S5)** — Title "From topic to citable report"; Gloss
    "验证 6：单 topic 端到端闭环".
    - `[H]` **One topic becomes a verifiable report for about a cent, and a cached rerun is free** —
      **100%** of claims citable · report 8.9k–10.8k characters with **16–23** claims · cold start
      **$0.0036–0.0126** in 60–91 s · cached rerun **$0 in 0.1 s**
    - `[1]` How we measured — 测量方法
      - `[2]` one HTTP request fetched 24 real OpenAlex records with abstracts; the full chain then ran
        locally — normalise, dedup, chunk, store, retrieve, LLM card extraction, LLM report, citation
        check, events — with cost and latency read from the event log; the run was then repeated against
        a warm cache to separate API cost from model cost
    - `[1]` Formulas — 计算公式
      - `[F]` `cost_run = Σ(tokens_in × p_in + tokens_out × p_out)` → 单次成本累加
      - `[F]` `citable_rate = citable_claims / claims = 1.0` → 可回查引用率
      - `[F]` `saving = 1 − cost_cached / cost_cold = 1` → 缓存节省
    - `[1]` Results — 实测结果
      - `[2]` report **8.9k–10.8k characters**, **16–23 claims**, all citable; cold start
        **$0.0036–0.0126** in 60–91 s; cached rerun **$0 in 0.1 s** with byte-identical claims;
        **33–34 events** per run
    - `[1]` Impact — 结论影响
      - `[2]` the loop is feasible and cheap; the gateway must detect reasoning-model truncation, which
        otherwise returns an empty body that looks like a success
    - `[3]` A `deepseek-flash` call with a small `max_tokens` returns `finish_reason=length` and empty
      content — caught by the gateway and retried with a larger budget
    - Takeaway: "Loop feasible and cheap".
20. **Verification 7 — guards and injection (S6)** — Title "Do the guards fire, and only then?"; Gloss
    "验证 7：守卫与故障注入".
    - `[H]` **Every injected fault was caught, once, with no false alarms** — detection **1.00** across
      five fault families × 3 runs (15/15) · false positives **0/3** on normal runs · thresholds
      **block 0.0777 / warn 0.0867**, set from the score distributions rather than guessed
    - `[1]` How we measured — 测量方法
      - `[2]` calibrated the drift thresholds first on real corpora — 24 on-topic papers against 8 real
        off-topic papers, with an honest hold-out (the first 15 build the centroid by leave-one-out, the
        last 9 are held back as the inspected artefacts) — then injected six scenarios three times each,
        entirely offline, because a guard is a pure function of its observed values and needs no LLM to
        exercise
    - `[1]` Formulas — 计算公式
      - `[F]` `block = (min_on + max_off) / 2 = (0.0885 + 0.0670) / 2 = 0.0777` → 阈值取分布间隙中点
      - `[F]` `warn = min_on × (1 − margin) = 0.0885 × 0.98 = 0.0867` → 预警取正样本下界
      - `[F]` `separable ⟺ min_on > max_off` → 可分性判据
      - `[F]` `TPR = TP / (TP + FN)` · `FPR = FP / (FP + TN)` → 检出率与误报率
    - `[1]` Results — 实测结果
      - `[2]` with the seed-corpus centroid the two distributions separate — on-topic
        **0.0885–0.2149** (mean 0.1405) against off-topic **0.0330–0.0670** (mean 0.0511), a gap of
        **0.0215** — giving TPR 1.0 / FPR 0.0; five fault families each detected **3/3**; the budget
        scenario showed 80% warn then 100% stop
    - `[1]` Impact — 结论影响
      - `[2]` scope representation and threshold calibration became frozen rules, and the retrieval
        scorer was unified with the guard scorer
    - `[3]` Counter-example kept for the talk: with a keyword-string scope the distributions overlapped
      (0.000–0.165 against 0.000–0.029) and **no threshold worked** (thr 0.02 gave TPR 0.88 / FPR 0.29);
      also banned by rule — `warn = block × k`, because the first version's `warn = 0.0777 × 1.5 = 0.12`
      sat inside the on-topic distribution and produced **3/3 false alarms** on normal runs
    - Takeaway: "Guards proven".
21. **Verification 8 — metrics (S7)** — Title "Can the numbers be recomputed from events?"; Gloss
    "验证 8：指标可从事件复算".
    - `[H]` **Every headline number is recomputed from events alone and reproduces by hand** — grounding
      **0.7949** (31/39) · hallucination **0.2051** (8/39) · cost **$0.006294** per run · hand check
      **16** supported / **1** contradicted / **6** unsupported / **23** verifiable
    - `[1]` How we measured — 测量方法
      - `[2]` aggregated five metrics from the event log only, never from summary files, over a defined
        campaign (the last 3 runs per scenario, the last 2 report runs and the cold start); then
        hand-checked one run against its raw claim file and aligned every formula with the evaluation
        plan
    - `[1]` Formulas — 计算公式
      - `[F]` `grounding = supported / verifiable = 31 / 39 = 0.7949` → 支持率
      - `[F]` `hallucination = (contradicted + unsupported) / verifiable = 8 / 39 = 0.2051` → 幻觉率
      - `[F]` `severe = contradicted / verifiable = 2 / 39 = 0.0513` → 严重幻觉率
      - `[F]` `topicality = mean(cos(claim, scope)) = 0.0699` → 主题相关度
      - `[F]` `cost_mean = Σ cost / runs = $0.006294` → 单次平均成本
    - `[1]` Results — 实测结果
      - `[2]` citation-resolvable rate **1.0**; injection TPR **1.0**; false-positive rate **0.0**;
        cold-start cost max **$0.012589**; the hand check matched the independent statistic exactly
    - `[1]` Impact — 结论影响
      - `[2]` three missing instrumentation points were added; the metric campaign is now scoped
        explicitly; independent verification (gold fact set plus a cross-vendor judge) is next
    - `[3]` Caveat: Phase 0 support labels are model-self-reported (`support_label_source=llm_self_label`),
      so grounding **0.7949** is not yet independently verified; the deterministic citation-resolvable
      rate **1.0** is the hard lower bound
    - Takeaway: "Numbers auditable".

**Presentation logic** — Answer-first: every slide title carries its message, the `[H]` hero states the
claim and its evidence in words, the takeaway strip closes the loop. One idea per slide; at most one
hero per slide, and never a bare number. Comparisons
are visual tables with semantic chips (chosen = filled accent chip, alternative = neutral outline chip,
rejected = muted grey chip). Slide 7 is a diagram, never prose. Slides 8–13 keep the two-column
Problem / Methods layout with a mechanism hero and an `→ evidence` cross-reference — mechanism, methods
and Chinese term glosses only, **no measured numbers**. Slides 14–21 keep the four fixed bands
`How we measured · Formulas · Results · Impact` — implementation detail, the arithmetic behind every
headline figure, and the measured result — with no `Why` block. So the module pairs read as
"what we do" (8–13) and "how we know it works, and by what computation" (14–21). Let tier weight be
visible at a glance: a reader who only sees the hero and the takeaway should still get the message of
every slide.

**Density** — Moderate and layered: hero + takeaway + 2–4 `[1]` blocks carry the page; `[2]` detail
fills the middle; `[3]` footnotes stay grey and at the foot of their block. Slides 3, 4 and 7 are
structurally dense but textually light. Outer margin ≥ 40 px; whitespace between blocks; never let
`[2]`/`[3]` compete with `[H]`.

**Style** — Modern technical-review minimalism (same system as the earlier selection deck):
- 16:9, `1280×720`; flat pages, free design, no template workspace.
- Palette: background `#FFFFFF`, surface `#F8FAFC`, hairline `#E2E8F0`, ink `#0F172A`, muted `#64748B`,
  footnote `#94A3B8`, accent `#2563EB`, accent-soft `#DBEAFE`, neutral chip `#F1F5F9`.
- Typography: Arial for English, Consolas only for technical tags and `[F]` formulas, CJK-safe sans
  (Microsoft YaHei) for every Chinese line.
  **Sizes (A-scale, px on the 1280×720 canvas; 1 px = 0.75 pt): cover 58 · title 40 · hero claim 26–28
  (verification heroes may reach 40) · hero evidence 19 · block header 24 · `[1]` line 21 · body / table /
  `[2]` / `[3]` / gloss / takeaway / `[F]` 19–21. Nothing below 19 px = 14.25 pt.**
- Chrome: accent tick + title top-left with the gloss beneath it, hairline rule, deck short-title
  bottom-left, page number bottom-right (`07 / 21`). Identical on every page.
- Motifs: 1 px hairlines, left accent ticks, aligned grids, small geometric vector icons. No photos,
  no AI images, no emoji.

**Output** — Export **Slides 1–4** to `exports/` as a native editable PPTX for the first-round check;
in the second round export the complete 21-slide deck **with speaker notes** to
`docs/ppt/2026-10-14-group-meeting/` (`--quick-generate --with-notes -o <path>.pptx`), where each slide's
note is that roster entry's full sentence (see the rendered-form contract above). After export, report:
deck path, resolved style/palette, which element was the `[H]` hero on each slide, how many
`[1]`/`[2]`/`[3]`/`[F]` items you rendered, the minimum run size found in the exported PPTX, how the
Chinese gloss is styled, and anything you simplified.

===== END PROMPT =====

## 第二轮（样例通过后）

把 **Roster** 换成 Slide 5–21，并追加一句：

```
Continue the same deck, same style system, chrome, bilingual rule and importance tiers ([H] one hero,
[F] 1–5 formulas per verification page; [1] 1–4 primary blocks, [2] supporting detail, [3] footnotes;
drop [3] first when space is tight, never `[F]`). **Nothing renders below 19 px (14.25 pt).**
Keep Slides 1–4 unchanged; author Slides 5–21 from the Roster in
docs/ppt/2026-10-14-group-meeting/group-meeting-ppt-prompt.md, following the fixed layouts: Slide 7 is
the node diagram; Slides 8–13 use two columns Problem / Methods (mechanism only, no measured numbers,
Chinese term glosses, `→ evidence` at the block foot); Slides 14–21 use the four fixed blocks
How we measured / Formulas / Results / Impact (no `Why`), with each `[F]` formula and its Chinese gloss
rendered as a small block. Export the complete 21-slide PPTX.
```

---

## 附录 C：Hero 写法（v3，按模块区分）

> 规则：hero 一律是「claim 句 + 证据行」，**不得出现裸数字**。模块决定 hero 的内容：
> - **问题页 8–13 = 机制 hero，纯文字、无测量数字**（数字全部迁到对应验证页）；
> - **验证页 14–21 = 结论 hero，claim 句 + 带含义的数字**；
> - 第 1、3–7 页的 hero 是结构/图表（封面、模块表、LangChain 色带、编排列、网关列、节点图），**不改**。

| # | Claim（≤18 词，无数字） | Evidence（数字 + 含义；问题页此列为机制要件） |
|---|---|---|
| 2 | Phase 0 meets its targets: fast stores, precise guards, cheap runs | graph 2-hop p95 **4.42 ms** (three stores hold 5k papers, 64.9 MB) · **15/15** injected faults detected, **0** false alarms · **$0.006** per run, 100% of claims citable |
| 8 | Scope is a versioned object, and drift is a calibrated distance | Mechanism hero — **words only, no measured numbers**: the anchor, the seed-corpus centroid, the stage contracts and the hard limits in code |
| 9 | A loop is replanned once, then stopped by the state machine | Mechanism hero — **words only**: signature window, state hash, zero facts delta, bounded back-edges, escalation ladder |
| 10 | The budget ladder is a diagram: four meters, degrade early, warn, stop | Diagram hero — the ladder itself; **no measured numbers on this page** |
| 11 | Factuality is enforced by contract, not by tone | Mechanism hero — **words only**: claim + citation as one unit, resolvable citations, contradictions and refusals kept first-class |
| 12 | State holds summaries and pointers; folding is an explicit node | Mechanism hero — **words only**; the honest "not yet measured" status stays as a `[3]` |
| 13 | Six validation layers, and the first four need no LLM | Mechanism hero — **words only**: L0–L5 named, fail-closed stated as policy |
| 14 | The whitelist does reach our target venues, and arXiv is indexed there | **386** papers / **3 years** (≈129/yr, a floor) · arXiv-in-OpenAlex **91.7%** · relevance **10/10** · **20/20** HTTP 200, p50 1.09 s |
| 15 | Both retrieval strategies are needed, with a stronger dedup key | overlap **0.004–0.014** · duplicates **19.3–19.8%** · reference completeness **1.5% / 14.3%** against broad **25–27%** |
| 16 | Three stores hold 5,000 papers with no swap needed | graph 2-hop p95 **4.42 ms** · author aggregation p95 5.06 ms · re-import growth **0** · **64.9 MB** disk |
| 17 | Vector latency is a deployment choice, not a design flaw | pure math **0.65 ms (0.3%)** · payload filtering **+140 ms (74%)** · local mode has **no ANN**, so it is exact kNN |
| 18 | Resuming at the node boundary reproduces the run; replaying the input does not | final state **identical** field by field · events **1..N** across 3 kills · checkpoint **28–37 KB** (≈4 KB per super-step) |
| 19 | One topic becomes a verifiable report for about a cent | **100%** of claims citable · 8.9k–10.8k characters, **16–23** claims · **$0.0036–0.0126** cold in 60–91 s · **$0** cached |
| 20 | Every injected fault was caught, once, with no false alarms | detection **1.00** (15/15) · false positives **0/3** · thresholds **0.0777 / 0.0867** from the score distribution |
| 21 | Every headline number is recomputed from events and reproduces by hand | grounding **0.7949** (31/39) · hallucination **0.2051** (8/39) · **$0.006294** per run · hand check 16 / 1 / 6 / 23 |

---

## 检查要点（验收样例时看这些）

- **hero 是否自解释**：每页最多一个 `[H]`；出现**裸数字对**（如 `1.00 / 0` 配两个词的标签）即为不合格
  —— 先补成完整意思，补不出来就**删掉卡片**把事实并入 `[2]`/`[3]`；**问题页 8–13 的 hero 必须是纯文字
  机制句，出现任何测量数字即为不合格**（数字属于对应验证页）；验证页 hero 必须是「claim 句 + 带含义的
  数字」；
- **层次是否靠颜色而非字号**：`[1]` 24 px / 21 px → `[2]` 19 px `#64748B` → `[3]` 19 px `#94A3B8`，
  靠字色、字重、位置区分；**任何元素低于 19 px（14.25 pt）即为不合格**（换算：1 px = 0.75 pt）；
- **每页配额**：`[1]` 1–4 条、`[2]` ≤8 条、`[3]` ≤6 条、`[F]` 1–5 条；正文约 60–120 词
  （对比页偏少、论证/验证页偏多）；片段不成句；
- **层次结构**：L1 英文标题（即结论）→ L1.5 一行灰字中文注解 → L2 块标题 → L3 片段 → L4 hero →
  L4.5 脚注 → L5 底部 takeaway（除封面外每页必有且逐字一致）；
- **中文是否只出现在四处**（标题下注解 / 术语首次括注 / 问题页方法行末尾 ≤8 字机制括注 / 验证页四个块
  标题下与每条公式下的中文注解）——表格单元格、图表标签、chip、公式内部出现中文即为不合格；
- **验证页公式是否给全**：第 14–21 页每页都必须有 `Formulas` 块，公式是纯文本、与
  `prototype/RESULTS.md` 口径一致，并各自带一行 ≤12 字中文说明；第 20 页必须出现
  `block = (min_on + max_off) / 2` 与 `warn = min_on × (1 − margin)`，**不得**出现 `warn = block × k`；
- 第 4 页是否为**一张**"LangChain 各模块 vs 本项目"对比表（8 行，单元格 ≤4 词，"What it is" 列做视觉强调）；
- 第 7 页是否为**节点串联图**（S0–S9 + 5 个守卫菱形 + 4 条回退箭头 + checkpoint 主线），而非文字列表；
- 第 8–13 页是否每页一个问题、统一两栏 Problem / Methods + 机制 hero + `→ evidence` 交叉引用；
  第 14–21 页是否每页一个验证、统一四块 How we measured / Formulas / Results / Impact（**无 Why 块**）；
- 数字是否与 `docs/ppt/2026-10-14-group-meeting/group-meeting-outline.md` 一致
  （4.42 ms / 155 ms / 1.00 / 0 / 0.7949 / $0.006294 / 0.0777 / 91.7% / 19.3–19.8%）；
- 是否**没有出现**源文件之外的数字或技术名（防幻觉）；
- **导出后必须实测 PPTX**（不要只看 SVG）：`python docs/ppt/scripts/verify-pptx.py <pptx>` 应报 21 页、备注
  21/21、**最小 run ≥ 14 pt**；同时 `python docs/ppt/scripts/svg-layout-check.py .agents/projects/<proj>/svg_output`
  必须 0 issue。v4 实测：21 页、最小 **14.2 pt**、notes 21/21、版式 0 冲突。
- 成品：`docs/ppt/2026-10-14-group-meeting/2026-10-14-group-meeting.pptx`
  （同一 md 的渲染源在 `.agents/projects/gm1013v4_20261013/`，页面生成器
  `docs/ppt/scripts/build-deck-pages.py` + `docs/ppt/scripts/deck_content.py`）。
