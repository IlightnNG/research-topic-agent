# Slide Deck Brief — Module & Framework Selection

> **Purpose:** group-meeting review of module-level framework selection for the Literature Research Assistant
> **Audience:** supervisor + research group · **Language:** English · **Aspect:** 16:9 · **Target:** 15 slides, 15–20 min
> **Structure:** system context → architecture → module map → module-by-module selection (choice + mainstream alternatives + rationale) → challenges & self-correction → evaluation preview → roadmap & decisions
> **Source of truth:** `project/framework-selection.md` (v0.4), `design/architecture-overview.md`, `design/challenges-and-self-healing.md`, `implementation/evaluation-plan.md`
> **Design notes:** one idea per slide · short noun phrases, not sentences · use the comparison tables as the visual centrepiece · one architecture diagram on Slide 3 · avoid code
> **How to read this file:** every `## Slide N` block = one PPT page. `Visual` and `Speaker note` lines are production hints, not slide copy.

---

## Slide 1 · Title

**Title:** Intelligent Multi-Agent Literature Research Assistant
**Subtitle:** Module & Framework Selection — Context & Harness Engineering
**Meta line:** EE5003 MSc Project · [Presenter] · [Date] · NUS

**Visual:** clean title page; small system tagline strip (Weekly runs · Paper relations · Three interfaces · Dual engine · Built-in evaluation)
**Speaker note:** One sentence framing: "This deck answers one question — which framework for each module, and why."

---

## Slide 2 · What the System Must Do

**Key message:** A weekly, unattended, self-correcting research agent — not a one-shot chatbot.

**Content**
- **Weekly autonomous runs** per user-managed topic → latest papers → long run → report
- **Self-correction:** no wrong-direction drift, no loops, no topic deviation
- **Paper relations + author activity:** who is active, how research directions evolve
- **Three interfaces:** Topic manager · Run report (process replay) · Chat
- **Dual engine:** local LLM + cloud API, with circuit breaking and fallback
- **Evaluation built in from day one** (hallucination, accuracy, drift)
- **Domain:** English literature · CS / software-hardware / engineering (NUS)

**Visual:** six requirement icons in a 2×3 grid
**Speaker note:** Emphasise that reliability over long horizons is the core requirement, not retrieval quality alone.

---

## Slide 3 · End-to-End Architecture

**Key message:** Deterministic control flow lives in the orchestrator; agents only produce structured artifacts.

**Content** (top → bottom)
1. **Interfaces** — FastAPI REST + SSE · Vue/React Web UI
2. **Application services** — Topic · Run/Job · Chat · Graph · Evaluation
3. **Orchestration** — LangGraph weekly pipeline + chat agent
4. **Context engineering** — token budget · folding · retrieval injection
5. **Model layer** — LiteLLM gateway → local engines / DeepSeek cloud
6. **Domain services** — retrieval · graph & vector IO · reporting · parsing
7. **Storage & sources** — SQLite · Kuzu · Qdrant · OpenAlex / arXiv / whitelist

**Visual:** single layered architecture diagram, left-to-right flow for a weekly run
**Speaker note:** Point out the one cross-cutting spine: the event log (single source of truth for replay, evaluation, audit).

---

## Slide 4 · Module Map — Final Selections

**Key message:** Ten modules, each with one clear primary choice and a defined fallback.

| # | Module | Final selection |
|---|---|---|
| 1 | Orchestration & multi-agent | **LangGraph** |
| 2 | LLM gateway & routing | **LiteLLM (SDK) + thin policy layer** |
| 3 | Local inference engine | **Ollama (dev) / vLLM (prod)** |
| 4 | Graph store | **Kuzu (embedded)** |
| 5 | Vector store & RAG | **Qdrant (local mode)** |
| 6 | Sources & parsing | **OpenAlex-first + arXiv + PyMuPDF** |
| 7 | Scheduling & long runs | **APScheduler + LangGraph + job registry** |
| 8 | Web backend | **FastAPI + SQLAlchemy + Alembic + SSE** |
| 9 | Web frontend | **Vue3 or React + TS + Vite + ECharts** |
| 10 | Evaluation & observability | **DeepEval shell + custom domain metrics** |

**Visual:** table as the slide body; highlight the two "framework-first" changes (2 and 10)
**Speaker note:** Next seven slides justify rows 1–10 in detail; each also names mainstream alternatives we deliberately did not adopt.

---

## Slide 5 · Module 1 — Orchestration & Multi-Agent

**Final choice:** **LangGraph** (weekly pipeline = explicit state graph; chat = ReAct agent)

| Option | Role | Pros | Cons / Why not now |
|---|---|---|---|
| **LangGraph** | Chosen | Explicit graph + conditional edges = visible, testable self-correction; built-in checkpointing (SQLite) for long runs; streaming events; largest agent ecosystem | API evolves fast → pin versions |
| AutoGen | Mainstream alternative | Strong free-form multi-agent conversation (research-style teams) | Conversational control flow; weaker for a controlled weekly pipeline |
| CrewAI | Mainstream alternative | Fastest to prototype role-based crews | Less deterministic; black-box orchestration; long-run recovery weak |

**Why this choice:** our self-correction requirements map directly onto graph nodes and conditional edges; checkpointing and streaming are provided, not rebuilt.
**Note:** classic LangChain not adopted — after modularisation its layers are covered by more focused components (LangGraph for agents, LiteLLM for models, official clients for stores), so the full framework would only add coupling.
**Scale-up path:** same framework; switch checkpointer store to PostgreSQL when needed.
**Visual:** mini pipeline graph (retrieval → map → analyse → report) with a feedback edge

---

## Slide 6 · Modules 2–3 — Model Layer: Gateway + Local Engines

**Final choice:** **LiteLLM** (SDK router in-process) + thin policy/audit layer · local engines **Ollama** (dev) / **vLLM** (Linux production) / **llama.cpp** (no-GPU fallback) · cloud **DeepSeek**

| Option | Role | Pros | Cons / Why not now |
|---|---|---|---|
| **LiteLLM** | Chosen gateway | One OpenAI-style interface for 100+ providers; fallbacks, retries, load balancing, cost tracking maintained upstream; SDK → self-hosted proxy | One abstraction layer → pin versions |
| Self-built thin gateway | Rejected | Zero dependency, fully controlled | Retry/circuit-breaker/cost/multi-vendor all become our maintenance burden |
| OpenRouter | Rejected | Zero-ops cloud aggregation | Third-party relay: data leaves the premises; cannot front local engines |
| **vLLM** / SGLang | Local serving | vLLM: throughput + continuous batching, production standard | SGLang: smaller ecosystem; vLLM: Linux-only (dev stays on Ollama) |

**Why this choice:** local engines and DeepSeek are all OpenAI-compatible → the gateway unifies protocol while **sensitivity routing stays in our code** (hard allow/deny, not a prompt rule).
**Scale-up path:** LiteLLM SDK → self-hosted proxy; vLLM scales to multi-GPU.
**Visual:** one gateway box fanning out to three providers, with a policy filter drawn *before* the fan-out

---

## Slide 7 · Modules 4–5 — Storage: Three Engines, Three Question Types

**Final choice:** **SQLite** (relational core) · **Kuzu** (graph) · **Qdrant** (vector)

| Engine | Answers | Architecture | Mainstream alternative — and why not now |
|---|---|---|---|
| **SQLite** | Run records, events, reports, chat, metrics | Row store + ACID, SQLAlchemy + Alembic | PostgreSQL later: richer concurrency at scale |
| **Kuzu** | Author dynamics, citation and co-authorship paths | Embedded, in-process, columnar + vectorised execution, zero network, MIT | Neo4j: JVM service, Bolt protocol, GPLv3 — worth it only at millions of nodes / multi-user / graph algorithms |
| **Qdrant** | "Which papers are semantically closest?" | Rust single engine: embedded → server → cluster, same product line | Milvus: cloud-native multi-component (etcd, object store) — overkill for 10⁴ vectors |

**Why this choice:** relationships, similarity and operational records are three different query types; each engine answers its own question, and all three are embedded (zero external services on one machine).
**Design rule:** write once (ingest pipeline), project three ways; unified by `paper_id`; the SQLite event table is the source of truth for replay and evaluation.
**Scale-up path:** all three are isolated behind service interfaces (SQLite→PG, Kuzu→Neo4j, Qdrant local→server).
**Visual:** one ingest arrow splitting into three store icons, each labelled with a sample query

---

## Slide 8 · Module 6 — Data Sources & Parsing

**Final choice:** **OpenAlex-first, arXiv-second** + custom venue whitelist · `pyalex / arxiv / httpx` + `PyMuPDF (+pdfplumber)` · self-built normalisation glue

| Aspect | Decision | Rationale |
|---|---|---|
| Primary source | **OpenAlex** | Indexes IEEE/ACM conference & journal papers (systems, hardware, EDA) with citation links and OA locations |
| Secondary source | **arXiv** | Fastest-moving preprints; category whitelist for freshness |
| Custom sources | Venue whitelist (OpenAlex `source.id`) + arXiv categories | Data-driven config — no new code path per venue |
| Text parsing | PyMuPDF primary, pdfplumber fallback | Light dependencies, robust on OA PDFs |
| Deferred | Unstructured / Docling / GROBID | Heavy dependencies; needed only for full-text citation graphs or complex layouts |

**Self-build boundary:** fetch protocols, PDF extraction, OCR and embeddings come from existing libraries; what we build is the **domain glue** — adapter interface, field mapping, canonical ID (DOI → OpenAlex W → arXiv), author keys, incremental cursors, idempotent upsert, chunking policy.
**Constraint to note:** non-OA (paywalled) papers are abstract-only; hardware literature rarely appears on arXiv — hence OpenAlex-first.
**Visual:** source → adapter → unified Paper model → three stores, with a "paywall" marker on the abstract-only branch

---

## Slide 9 · Module 7 — Scheduling & Unattended Runtime

**Final choice:** **APScheduler** (weekly cron trigger) + **LangGraph** (run execution) + thin DB-backed job registry + event stream to the UI

| Option | Role | Pros | Cons / Why not now |
|---|---|---|---|
| **APScheduler + job registry** | Chosen | Trigger + run state + per-topic lock + watchdog, all persisted next to the Web event stream | No distributed execution |
| Celery + Redis | Mainstream alternative | Mature distributed task queue | Broker/worker ops; weekly low-frequency runs do not need it; overlaps with LangGraph |
| Prefect / Dagster | Mainstream alternative | Rich scheduling, retries, UI | Heavy stack; duplicates graph orchestration |
| Temporal | Future option | Industrial durable execution for long tasks | Server cluster required — reconsider only at platform scale |

**Why this choice:** the run's execution logic already lives in LangGraph; what remains is bookkeeping (state, locks, cancellation, events), which we keep thin and local.
**Scale-up path:** submit runs as Celery tasks or Temporal workflows if the system becomes multi-machine / multi-tenant.
**Visual:** timeline of a weekly run with watchdogs; side box for manual re-run

---

## Slide 10 · Modules 8–9 — Interfaces: Backend & Frontend

**Final choice:** **FastAPI + SQLAlchemy 2.0 + Alembic + SSE** · **Vue3 or React + TypeScript + Vite + ECharts**

| Option | Role | Pros | Cons / Why not now |
|---|---|---|---|
| **FastAPI** | Chosen backend | Async-native; SSE/WebSocket natural; Pydantic shared by agent protocol *and* API schema; auto OpenAPI | No built-in background jobs (covered by Module 7) |
| Django REST | Mainstream alternative | Batteries-included, mature admin | Sync ORM vs long-lived streaming; heavy boilerplate for three real-time views |
| **Vue3 / React** | Chosen frontend | Both mainstream; isolated behind REST/SSE so the choice is low-risk | Pick by team familiarity |
| Next.js | Rejected | Full-stack React | Backend is FastAPI — a Node stack would duplicate it |
| AntV G6 / Cytoscape.js | Future option | Strong for large graphs and custom interactions | ECharts is enough for topic subgraphs today |

**Interface contract:** Topic CRUD · run records + live event stream · report history · chat with streaming answers · graph/author queries.
**Scale-up path:** multiple uvicorn workers + PostgreSQL; swap the graph renderer when interaction complexity grows.
**Visual:** three UI mock panels (Topic / Report timeline / Chat) side by side

---

## Slide 11 · Module 10 — Evaluation & Observability Stack

**Final choice:** **DeepEval** (LLM-judge & standard metrics shell) + **custom domain metrics** (guards, drift, grounding) + event-sourced replay

| Option | Role | Pros | Cons / Why not now |
|---|---|---|---|
| **DeepEval** | Chosen shell | Faithfulness/groundedness metrics and custom metrics out of the box; pytest-style regression | Version churn → pin |
| Custom domain module | Required | Drift, self-healing and guard metrics that no framework provides; same event table as replay/audit | Scope kept deliberately small |
| ragas / promptfoo | Alternatives | RAG-oriented metrics / file-based regression and red-teaming | Complementary, optional |
| LangSmith | Rejected | Integrated tracing + eval | SaaS, paid, data leaves premises |
| LangFuse | Future option | Self-hosted LLM observability | Requires PostgreSQL/Redis — revisit once the system is service-scale |

**Why this choice:** standard metrics come from the framework; the parts that define the thesis' methodology (drift, self-healing, grounding) remain ours and run on the same event source.
**Visual:** pipeline of run → events → metrics → paper charts

---

## Slide 12 · Key Challenges & Planned Solutions

**Key message:** The hard parts are long-horizon reliability and relationship analytics — both have designed mitigations.

| Challenge | Why it is hard | Planned approach |
|---|---|---|
| **Topic drift in long runs** | A single early error compounds across hours | Scope-anchor injection, drift detectors, conditional-edge rollback to planning |
| **Loops & stagnation** | Unattended runs silently waste time and cost | Tool-signature cycle detection, no-progress detection, forced replan |
| **Context growth / VRAM** | Long runs inflate state; local budgets are tight | Structured state + summarisation folding + budget-driven routing to cloud |
| **Author relation analytics** | Name ambiguity; time semantics | Metadata-level temporal graph first; disambiguation deferred with merge keys reserved |
| **Unattended operations** | Crashes, overlapping runs, storage growth | Per-topic locks, watchdog timeouts, interrupted-run recovery, retention policy |
| **Provenance & replay** | Evaluation needs ground truth | Event sourcing as the single source of truth |

**Visual:** two-column layout — challenge icons left, mitigation arrows right
**Speaker note:** These are the areas where thesis contributions are measured, not just engineered.

---

## Slide 13 · Self-Correction Design (Supervisor Focus)

**Key message:** Reliability is enforced by the harness, not by asking the model to "be careful".

**Three lines of defence**
1. **Runtime guards** — evaluated around every node → prevent going off-track
2. **State-machine discipline** — structured outputs, timeouts, turn limits, checkpoint recovery → prevent runaway
3. **Post-run quality gate** — grounding check + judge score → prevent poor output from passing

**Detectors & responses**

| Detector | Signal | Response |
|---|---|---|
| Topic drift | Scope embedding similarity below threshold | Return to planning with feedback |
| Retrieval drift | Share of out-of-scope results | Tighten query, re-retrieve |
| Loop | Repeated tool-call signature cycle | Forced replan |
| Stagnation | Zero new verified facts | Retry → switch provider → stop with annotation |
| Schema / citation failure | Invalid structure, unverifiable citation | Retry once → degrade → annotate |

**Escalation ladder:** retry → degrade (provider/model) → replan → abort with annotation — never fail silently.
**Recovery detail:** each escalation injects "what failed + trusted state + next step" back into the agent context.
**Testability:** fault-injection hooks exist from Phase 2, so self-healing itself is measured (see next slide).

---

## Slide 14 · Evaluation Plan Preview — Datasets & Metrics

**Key message:** Evaluation is designed in, not bolted on: fixed datasets plus runtime instrumentation.

**Datasets**
- 3–5 fixed English topics with hand-built **gold fact lists** (20–40 verifiable facts each)
- Chat question sets across five types (factual · relational/author · survey/comparison · cross-topic · unanswerable)
- **Fault-injection scenarios** (drift, loop, stagnation, provider failure, hallucination bait)
- Frozen **corpus snapshots** so grounding checks stay reproducible

**Metrics**
- Faithfulness / grounding support rate; hallucination rate (unsupported or contradicted claims)
- Answer accuracy and recall against gold facts; citation correctness; refusal appropriateness
- Drift rate; self-healing **detection / correct-action / recovery rates**; out-of-scope side effects
- Local vs cloud paired comparison: quality, latency, token cost

**Protocol:** weekly runs ≥ 4 weeks · cross-source judge · human spot-check with agreement reporting · fixed sampling parameters
**Highlight:** a "guards off vs guards on" ablation quantifies the value of the self-correction layer.
**Visual:** metrics dashboard mock-up; datasets as four cards

---

## Slide 15 · Roadmap & Decisions Needed

**Roadmap (one line each)**
- **P1** Minimal closed loop: retrieval → store → report, with instrumentation
- **P2** Harness core: LangGraph pipeline, guards, watchdog, fault injection
- **P3** Multi-agent split + context folding + chat interface
- **P4** Weekly automation, novelty detection, author-dynamics views
- **P5** Evaluation campaign: ≥ 4 weeks of data, local vs cloud
- **P6** Context/Harness specification + thesis

**Decisions requested**
1. Approve **LangGraph + LiteLLM** as the framework-first combination
2. Approve the **DeepEval shell + custom domain metrics** split
3. Confirm **OpenAlex-first / arXiv-second**, venue whitelist, English-language reports
4. Confirm deployment machine and GPU tier (decides the local model profile)
5. Frontend preference: **Vue3 or React**
6. Optional: include a **DeepSeek Harness comparison** chapter

**Visual:** timeline bar for P1–P6; decision list in a numbered card column
**Speaker note:** Close by asking for feedback on the decisions; full comparison tables are in the written report.

---

> **Appendix (optional slide):** full per-module option matrices and references live in `project/framework-selection.md` (v0.4).
