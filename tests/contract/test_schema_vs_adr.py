"""表结构 ↔ ADR-0005 一致性：24 张表、部分唯一索引、幂等键列都要在。"""

from __future__ import annotations

from pathlib import Path

from lit_agent.db import tables

ADR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "implementation"
    / "adr"
    / "0005-entity-tables-and-event-keys.md"
)

EXPECTED = {
    # 12 修订
    "topics",
    "topic_sources",
    "runs",
    "run_events",
    "reports",
    "llm_calls",
    "metrics",
    "sync_state",
    "job_locks",
    "chat_sessions",
    "chat_messages",
    "eval_judgments",
    # 12 新增
    "store_meta",
    "papers",
    "papers_raw",
    "authors",
    "paper_authors",
    "citations",
    "paper_merges",
    "paper_chunks",
    "claims",
    "claim_citations",
    "llm_cache",
    "embeddings",
    # Phase 3.2（ADR-0009）
    "paper_cards",
    "report_steps",
    # Phase 3.4（ADR-0010）
    "metric_definitions",
    "metric_points",
    "run_spans",
    "experiments",
}


def test_table_set_matches_adr() -> None:
    assert set(tables.EXPECTED_TABLES) == EXPECTED


def test_every_table_is_documented_in_adr() -> None:
    adr_0009 = ADR.parent / "0009-report-v2-tables.md"
    adr_0010 = ADR.parent / "0010-metrics-tables.md"
    text = ADR.read_text(encoding="utf-8")
    for extra in (adr_0009, adr_0010):
        if extra.exists():
            text += "\n" + extra.read_text(encoding="utf-8")
    missing = sorted(
        name for name in EXPECTED if f"`{name}`" not in text and f"TABLE {name}" not in text
    )
    assert not missing, f"ADR-0005 未记录这些表：{missing}"


def test_partial_unique_indexes_exist() -> None:
    indexes = {index.name for index in tables.t_papers.indexes}
    assert "ux_papers_doi" in indexes
    assert "ux_papers_source" in indexes

    run_indexes = {index.name for index in tables.t_runs.indexes}
    assert "ux_runs_one_running" in run_indexes

    event_indexes = {index.name for index in tables.t_run_events.indexes}
    assert "ux_run_events_dedupe" in event_indexes


def test_partial_indexes_have_where_clause() -> None:
    for table, name in (
        (tables.t_papers, "ux_papers_doi"),
        (tables.t_runs, "ux_runs_one_running"),
        (tables.t_run_events, "ux_run_events_dedupe"),
        (tables.t_authors, "ux_authors_orcid"),
    ):
        index = next(ix for ix in table.indexes if ix.name == name)
        assert index.dialect_options["sqlite"]["where"] is not None, f"{name} 缺少 WHERE 子句"


def test_idempotency_columns_exist() -> None:
    assert "next_seq" in tables.t_runs.c
    assert "dup_events" in tables.t_runs.c
    assert "dedupe_key" in tables.t_run_events.c
    assert "content_sha" in tables.t_reports.c
    assert "request_sha" in tables.t_llm_cache.c
    assert "merged_ids_json" in tables.t_papers.c
    assert "merged_id" in tables.t_paper_merges.c


def test_metrics_primary_key_supports_recompute() -> None:
    pk = [col.name for col in tables.t_metrics.primary_key.columns]
    assert pk == ["scope", "scope_id", "metric"]
