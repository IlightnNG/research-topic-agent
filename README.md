# Research Topic Agent

An intelligent, multi-agent literature research assistant built on **Context
Engineering** and **Harness Engineering**.

Keeping pace with scientific literature is a foundational challenge for researchers.
This project develops an autonomous assistant that explores, tracks, and maps complex
research topics over time — running scheduled, unattended analysis instead of relying
on brittle single-prompt wrappers.

## Objectives

- **Topic tracking over time.** For each user-managed topic, run a scheduled pipeline:
  retrieve the newest literature → ingest and deduplicate → update the paper/author
  graph → analyse → write a weekly report.
- **Multi-agent orchestration.** Specialised sub-agents (retrieval, network mapping,
  scheduled update, analysis, reporting, quality review) working under one orchestrator
  toward a unified research goal.
- **Paper relations and author activity.** Model relationships between papers
  (citation, co-authorship, topical proximity, temporal) so a user can see who is
  active and how a research direction evolves.
- **Deterministic execution and self-correction.** Runtime guards, state-machine
  discipline, and a post-run quality gate detect and recover from topic drift, loops,
  and stagnation — failures are annotated, never silent.
- **Context Engineering.** Manage the flow and folding of active information so the
  right academic context enters the context window without exceeding VRAM limits.
- **Harness Engineering.** State machines, evaluation loops, document parsing
  runtimes, retry logic, data provenance, and full event replay around the agents.
- **Dual LLM engine.** Route reasoning between locally deployed open-source models
  (privacy-focused, cost-restricted) and cloud APIs, by task complexity and data
  sensitivity, with circuit breaking and fallback.

## Tech Stack

| Layer | Choice |
|---|---|
| Orchestration | LangGraph (scheduled pipeline as an explicit state graph) |
| LLM gateway | LiteLLM — Ollama / vLLM (local) + DeepSeek (cloud), with routing, circuit breaking, fallback |
| Backend | FastAPI, SQLAlchemy 2.0, Alembic, SSE |
| Frontend | Vue 3 or React + TypeScript + Vite + ECharts |
| Storage | SQLite (runs, events, reports) · Kuzu (paper/author graph) · Qdrant (vector search) |
| Data sources | OpenAlex (primary), arXiv, custom venue whitelist |
| Parsing | PyMuPDF, pdfplumber |
| Scheduling | APScheduler |
| Evaluation | DeepEval + in-house domain metrics (drift, self-healing, grounding) |
| Language | Python 3.11+ |

Single machine, no external services required — all stores are embedded or local.

