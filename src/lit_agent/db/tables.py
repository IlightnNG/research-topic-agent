"""24 张表的 DDL（契约 = `adr/0005-entity-tables-and-event-keys.md` §3）。

- 12 张**修订**：topics / topic_sources / runs / run_events / reports / llm_calls / metrics /
  sync_state / job_locks / chat_sessions / chat_messages / eval_judgments
- 12 张**新增**：store_meta / papers / papers_raw / authors / paper_authors / citations /
  paper_merges / paper_chunks / claims / claim_citations / llm_cache / embeddings

改动本文件 = 改契约 → 必须写 ADR 并同步 `structure.SCHEMA_VERSION`。
"""

from __future__ import annotations

from sqlalchemy import (
    REAL,
    Column,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)

from lit_agent.db.base import metadata

__all__ = [
    "ALL_TABLES",
    "EXPECTED_TABLES",
    "SCHEMA_VERSION",
    "t_authors",
    "t_chat_messages",
    "t_chat_sessions",
    "t_citations",
    "t_claim_citations",
    "t_claims",
    "t_embeddings",
    "t_eval_judgments",
    "t_job_locks",
    "t_llm_cache",
    "t_llm_calls",
    "t_metrics",
    "t_paper_authors",
    "t_paper_cards",
    "t_report_steps",
    "t_paper_chunks",
    "t_paper_merges",
    "t_papers",
    "t_papers_raw",
    "t_reports",
    "t_run_events",
    "t_runs",
    "t_store_meta",
    "t_sync_state",
    "t_topic_sources",
    "t_topics",
]

SCHEMA_VERSION = "1.0"

# --------------------------------------------------------------------------- #
# 3.1 库身份
# --------------------------------------------------------------------------- #
t_store_meta = Table(
    "store_meta",
    metadata,
    Column("store_name", String, primary_key=True),  # sqlite | kuzu | qdrant
    Column("schema_version", String, nullable=False),
    Column("app_version", String),
    Column("model_id", String),
    Column("model_rev", String),
    Column("dim", Integer),
    Column("active_collection", String),
    Column("built_at", String, nullable=False),
    Column("extra_json", Text),
)

# --------------------------------------------------------------------------- #
# 3.2 主题与抓取范围
# --------------------------------------------------------------------------- #
t_topics = Table(
    "topics",
    metadata,
    Column("id", String, primary_key=True),  # slug
    Column("name", String, nullable=False, unique=True),
    Column("description", Text),
    Column("scope_statement", Text, nullable=False),
    Column("scope_keywords_json", Text, nullable=False, server_default=text("'[]'")),
    Column("seed_queries_json", Text, nullable=False, server_default=text("'[]'")),
    Column("status", String, nullable=False, server_default=text("'active'")),
    Column("config_json", Text),
    Column("schedule_cron", String),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

t_topic_sources = Table(
    "topic_sources",
    metadata,
    Column("topic_id", String, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
    Column("source", String, nullable=False),
    Column("selector_json", Text, nullable=False),
    PrimaryKeyConstraint("topic_id", "source"),
)

# --------------------------------------------------------------------------- #
# 3.3 论文实体
# --------------------------------------------------------------------------- #
t_papers = Table(
    "papers",
    metadata,
    Column("paper_id", String, primary_key=True),
    Column("source", String, nullable=False),
    Column("source_id", String, nullable=False),
    Column("doi", String),
    Column("title", Text, nullable=False),
    Column("title_norm", Text, nullable=False),
    Column("abstract", Text),
    Column("year", Integer),
    Column("published_at", String),
    Column("venue_id", String),
    Column("venue_name", String),
    Column("is_oa", Integer, nullable=False, server_default=text("0")),
    Column("oa_pdf_url", String),
    Column("language", String),
    Column("parse_status", String, nullable=False, server_default=text("'pending'")),
    Column("n_chunks", Integer, nullable=False, server_default=text("0")),
    Column("cited_by_count", Integer),
    Column("merged_ids_json", Text, nullable=False, server_default=text("'[]'")),
    Column("source_updated_at", String),
    Column("row_updated_at", String, nullable=False),
    Column("created_at", String, nullable=False),
)

t_papers_raw = Table(
    "papers_raw",
    metadata,
    Column("raw_id", Integer, primary_key=True, autoincrement=True),
    Column("source", String, nullable=False),
    Column("source_id", String, nullable=False),
    Column("run_id", String),
    Column("fetched_at", String, nullable=False),
    Column("content_sha", String, nullable=False),
    Column("raw_json", Text, nullable=False),
    UniqueConstraint("source", "source_id", "content_sha"),
)

t_authors = Table(
    "authors",
    metadata,
    Column("author_id", String, primary_key=True),
    Column("name", Text, nullable=False),
    Column("name_norm", Text, nullable=False),
    Column("orcid", String),
    Column("works_count", Integer),
    Column("last_institution", Text),
    Column("source", String),
    Column("source_updated_at", String),
    Column("row_updated_at", String, nullable=False),
)

t_paper_authors = Table(
    "paper_authors",
    metadata,
    Column("paper_id", String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False),
    Column(
        "author_id", String, ForeignKey("authors.author_id", ondelete="CASCADE"), nullable=False
    ),
    Column("position", Integer, nullable=False),
    Column("is_corresponding", Integer, nullable=False, server_default=text("0")),
    PrimaryKeyConstraint("paper_id", "position"),
)

t_citations = Table(
    "citations",
    metadata,
    Column("citing_id", String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False),
    Column("cited_id", String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False),
    Column("source", String, nullable=False, server_default=text("'openalex'")),
    Column("first_seen_at", String, nullable=False),
    Column("run_id", String),
    PrimaryKeyConstraint("citing_id", "cited_id"),
)

t_paper_merges = Table(
    "paper_merges",
    metadata,
    Column("primary_id", String, nullable=False),
    Column("merged_id", String, nullable=False),
    Column("run_id", String),
    Column("reason", String),  # exact_id | fingerprint | fuzzy
    Column("created_at", String, nullable=False),
    PrimaryKeyConstraint("primary_id", "merged_id"),
)

t_paper_chunks = Table(
    "paper_chunks",
    metadata,
    Column("paper_id", String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False),
    Column("chunk_idx", Integer, nullable=False),
    Column("section", String),
    Column("text_sha", String, nullable=False),
    Column("token_count", Integer, nullable=False),
    Column("page_from", Integer),
    Column("page_to", Integer),
    Column("char_start", Integer),
    Column("char_end", Integer),
    PrimaryKeyConstraint("paper_id", "chunk_idx"),
)

# --------------------------------------------------------------------------- #
# 3.4 运行、事件与报告
# --------------------------------------------------------------------------- #
t_runs = Table(
    "runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("topic_id", String, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
    Column("trigger", String, nullable=False),
    # Phase 1.2 / S1：UI 口径 —— period（列表按周分组）、focus_hint（一次性子主题）、scope_sha（scope 快照）
    Column("period", String),
    Column("focus_hint", String),
    Column("scope_sha", String),
    Column("state", String, nullable=False),
    Column("stage", String),
    Column("last_ok_stage", String),
    Column("error_code", String),
    Column("next_seq", Integer, nullable=False, server_default=text("0")),
    Column("dup_events", Integer, nullable=False, server_default=text("0")),
    Column("config_snapshot_json", Text, nullable=False),
    Column("input_hash", String, nullable=False),
    Column("app_version", String),
    Column("started_at", String),
    Column("finished_at", String),
    Column("created_at", String, nullable=False),
)

t_run_events = Table(
    "run_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("ts", String, nullable=False),
    Column("type", String, nullable=False),
    Column("stage", String),
    Column("agent", String),
    Column("severity", String, nullable=False),
    Column("dedupe_key", String),
    Column("payload_json", Text, nullable=False),
    Column("schema_version", String, nullable=False),
    UniqueConstraint("run_id", "seq"),
)

t_reports = Table(
    "reports",
    metadata,
    Column("report_id", String, primary_key=True),
    Column("topic_id", String, ForeignKey("topics.id"), nullable=False),
    Column("run_id", String, ForeignKey("runs.id"), nullable=False),
    Column("period", String),
    Column("title", Text),
    Column("content_md", Text, nullable=False),
    Column("content_sha", String, nullable=False),
    Column("claims_json", Text),
    Column("sections_json", Text),
    Column("language", String),
    Column("generated_by", String),
    Column("word_count", Integer),
    Column("fallback_reason", Text),
    Column("metrics_snapshot_json", Text),
    Column("n_claims", Integer, nullable=False, server_default=text("0")),
    Column("degraded", Integer, nullable=False, server_default=text("0")),
    Column("created_at", String, nullable=False),
    UniqueConstraint("run_id", "content_sha"),
)

t_claims = Table(
    "claims",
    metadata,
    Column("claim_id", String, primary_key=True),
    Column("run_id", String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("report_id", String, ForeignKey("reports.report_id", ondelete="CASCADE")),
    Column("text", Text, nullable=False),
    Column("text_sha", String, nullable=False),
    Column("support", String, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("run_id", "text_sha"),
)

t_claim_citations = Table(
    "claim_citations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("claim_id", String, ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False),
    Column("paper_id", String, nullable=False),
    Column("chunk_idx", Integer, nullable=False, server_default=text("-1")),
    Column("snippet", Text),
    Column("score", REAL),
    UniqueConstraint("claim_id", "paper_id", "chunk_idx"),
)

# --------------------------------------------------------------------------- #
# 3.5 网关、缓存与向量
# --------------------------------------------------------------------------- #
t_llm_calls = Table(
    "llm_calls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", String, nullable=False),
    Column("run_id", String, ForeignKey("runs.id", ondelete="SET NULL")),
    Column("agent", String),
    Column("provider", String, nullable=False),
    Column("model", String, nullable=False),
    Column("route_reason", String),
    Column("request_sha", String, nullable=False),
    Column("cache_hit", Integer, nullable=False, server_default=text("0")),
    Column("req_tokens", Integer),
    Column("resp_tokens", Integer),
    Column("cost", REAL),
    Column("cost_estimated", Integer, nullable=False, server_default=text("0")),
    Column("latency_ms", Integer),
    Column("degraded", Integer, nullable=False, server_default=text("0")),
    Column("ok", Integer, nullable=False, server_default=text("1")),
    Column("error_code", String),
)

t_llm_cache = Table(
    "llm_cache",
    metadata,
    Column("request_sha", String, primary_key=True),
    Column("model", String, nullable=False),
    Column("response_json", Text, nullable=False),
    Column("usage_json", Text),
    Column("created_at", String, nullable=False),
    Column("hit_count", Integer, nullable=False, server_default=text("0")),
)

t_embeddings = Table(
    "embeddings",
    metadata,
    Column("text_sha", String, nullable=False),
    Column("model_id", String, nullable=False),
    Column("model_rev", String, nullable=False),
    Column("dim", Integer, nullable=False),
    Column("vec", LargeBinary, nullable=False),  # float32 little-endian，已 L2 归一化
    Column("created_at", String, nullable=False),
    PrimaryKeyConstraint("text_sha", "model_id", "model_rev"),
)

# --------------------------------------------------------------------------- #
# 3.6 指标、同步、锁、会话、评测
# --------------------------------------------------------------------------- #
t_metrics = Table(
    "metrics",
    metadata,
    Column("scope", String, nullable=False),  # run | topic | campaign | global
    Column("scope_id", String, nullable=False),
    Column("metric", String, nullable=False),
    Column("value", REAL, nullable=False),
    Column("meta_json", Text),
    Column("ts", String, nullable=False),
    PrimaryKeyConstraint("scope", "scope_id", "metric"),
)

t_sync_state = Table(
    "sync_state",
    metadata,
    Column("source", String, nullable=False),
    Column("selector", String, nullable=False),
    Column("last_cursor", String),
    Column("last_since", String),
    Column("last_success_at", String),
    Column("status", String, nullable=False),
    Column("error_code", String),
    PrimaryKeyConstraint("source", "selector"),
)

t_job_locks = Table(
    "job_locks",
    metadata,
    Column("topic_id", String, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    Column("owner", String, nullable=False),
    Column("acquired_at", String, nullable=False),
    Column("heartbeat_at", String, nullable=False),
    Column("expires_at", String, nullable=False),
)

t_chat_sessions = Table(
    "chat_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("topic_id", String, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String, nullable=False),
)

t_chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "session_id", String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    ),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("citations_json", Text),
    Column("run_id_ref", String),
    Column("ts", String, nullable=False),
)

t_eval_judgments = Table(
    "eval_judgments",
    metadata,
    Column("id", String, primary_key=True),
    Column("target_type", String, nullable=False),
    Column("target_id", String, nullable=False),
    Column("metric", String, nullable=False),
    Column("score", REAL, nullable=False),
    Column("judge_model", String),
    Column("human", Integer, nullable=False, server_default=text("0")),
    Column("detail_json", Text),
    Column("ts", String, nullable=False),
)

# --------------------------------------------------------------------------- #
# 索引（含部分唯一索引：SQLite 的 `WHERE` 子句）
# --------------------------------------------------------------------------- #
Index("ux_papers_doi", t_papers.c.doi, unique=True, sqlite_where=t_papers.c.doi.isnot(None))
Index("ux_papers_source", t_papers.c.source, t_papers.c.source_id, unique=True)
Index("ix_papers_title_norm", t_papers.c.title_norm)
Index("ix_papers_venue_year", t_papers.c.venue_id, t_papers.c.year)
Index("ix_papers_parse_status", t_papers.c.parse_status)
Index(
    "ix_papers_raw_lookup",
    t_papers_raw.c.source,
    t_papers_raw.c.source_id,
    t_papers_raw.c.fetched_at,
)
Index(
    "ux_authors_orcid",
    t_authors.c.orcid,
    unique=True,
    sqlite_where=t_authors.c.orcid.isnot(None),
)
Index("ix_authors_name_norm", t_authors.c.name_norm)
Index("ix_paper_authors_author", t_paper_authors.c.author_id)
Index("ix_citations_cited", t_citations.c.cited_id)
Index("ix_paper_merges_merged", t_paper_merges.c.merged_id)
Index("ix_runs_topic_created", t_runs.c.topic_id, t_runs.c.created_at)
Index(
    "ux_runs_one_running",
    t_runs.c.topic_id,
    unique=True,
    sqlite_where=t_runs.c.state == "running",
)
Index("ix_run_events_type_ts", t_run_events.c.type, t_run_events.c.ts)
Index(
    "ux_run_events_dedupe",
    t_run_events.c.run_id,
    t_run_events.c.dedupe_key,
    unique=True,
    sqlite_where=t_run_events.c.dedupe_key.isnot(None),
)
Index("ix_reports_topic_created", t_reports.c.topic_id, t_reports.c.created_at)
Index("ix_claims_run", t_claims.c.run_id)
Index("ix_claims_report", t_claims.c.report_id)
Index("ix_claim_citations_claim", t_claim_citations.c.claim_id)
Index("ix_claim_citations_paper", t_claim_citations.c.paper_id)
Index("ix_llm_calls_run", t_llm_calls.c.run_id)
Index("ix_llm_calls_ts", t_llm_calls.c.ts)
Index("ix_chat_messages_session", t_chat_messages.c.session_id, t_chat_messages.c.ts)
Index(
    "ix_eval_target",
    t_eval_judgments.c.target_type,
    t_eval_judgments.c.target_id,
    t_eval_judgments.c.metric,
)


t_paper_cards = Table(
    "paper_cards",
    metadata,
    Column("paper_id", String, primary_key=True),
    Column("content_sha", String, nullable=False),
    Column("version", Integer, nullable=False, server_default=text("1")),
    Column("card_json", Text, nullable=False),
    Column("created_at", String, nullable=False),
)

t_report_steps = Table(
    "report_steps",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String),
    Column("report_id", String),
    Column("step", String, nullable=False),
    Column("status", String, nullable=False),
    Column("duration_ms", Integer),
    Column("tokens", Integer),
    Column("cost_usd", REAL),
    Column("error_code", String),
    Column("meta_json", Text),
    Column("created_at", String, nullable=False),
)
Index("ix_report_steps_run", t_report_steps.c.run_id)

#: `metadata.sorted_tables`（按外键依赖排序），用于建表/删表
ALL_TABLES = metadata.sorted_tables

#: 期望存在的表名集合（doctor / 迁移测试用）
EXPECTED_TABLES: frozenset[str] = frozenset(table.name for table in metadata.tables.values())
