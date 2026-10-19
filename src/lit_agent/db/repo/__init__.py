"""仓储层：SQLite 的**唯一写入口**（业务代码不得直接拼 SQL 写库）。

模块划分与表一一对应：
`papers`（含 `papers_raw`）/ `authors`（含 `paper_authors`）/ `citations`（含 `paper_merges`）/
`topics`（含 `topic_sources`）/ `runs` / `events` / `reports` / `claims`（含 `claim_citations`）/
`sync` / `llm_calls`（含 `llm_cache`）/ `locks`。
"""

from __future__ import annotations

__all__ = [
    "authors",
    "citations",
    "claims",
    "events",
    "llm_calls",
    "locks",
    "papers",
    "reports",
    "runs",
    "sync",
    "topics",
]
