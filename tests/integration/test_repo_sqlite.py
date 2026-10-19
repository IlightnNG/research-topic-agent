"""仓储层验收：幂等、字段边界、外键过滤、锁与唯一约束（Step 1.3）。"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from lit_agent.db.repo import authors as author_repo
from lit_agent.db.repo import citations as citation_repo
from lit_agent.db.repo import claims as claim_repo
from lit_agent.db.repo import llm_calls as llm_repo
from lit_agent.db.repo import locks as lock_repo
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import reports as report_repo
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.repo import sync as sync_repo
from lit_agent.models.author import Author
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, Support
from lit_agent.models.paper import Paper
from lit_agent.models.report import Report
from lit_agent.models.run import RunState


def make_paper(
    paper_id: str = "10.1000/a", *, title: str = "T", merged: list[str] | None = None
) -> Paper:
    return Paper(
        paper_id=paper_id,
        title=title,
        source="openalex",
        source_id=f"W-{paper_id}",
        abstract="abstract text",
        merged_ids=merged or [],
    )


# --------------------------------------------------------------------------- #
# papers
# --------------------------------------------------------------------------- #
def test_paper_upsert_is_idempotent(seeded: Connection) -> None:
    paper_repo.upsert_many(seeded, [make_paper()])
    paper_repo.upsert_many(seeded, [make_paper()])
    assert paper_repo.count(seeded) == 1


def test_paper_upsert_respects_derived_field_boundary(seeded: Connection) -> None:
    paper_repo.upsert_many(seeded, [make_paper(merged=["W-old"])])
    paper_repo.set_parse_status(seeded, "10.1000/a", "ok", n_chunks=3)

    # 源侧重新抓取：标题更新，但"解析状态 / 分块数 / 合并关系"属于本地派生，不得被覆盖
    paper_repo.upsert_many(seeded, [make_paper(title="T2")])

    row = paper_repo.get(seeded, "10.1000/a")._mapping
    assert row["title"] == "T2"
    assert row["parse_status"] == "ok"
    assert row["n_chunks"] == 3
    assert "W-old" in row["merged_ids_json"]


def test_papers_raw_dedupes_identical_payload(seeded: Connection) -> None:
    record = {
        "source": "openalex",
        "source_id": "W1",
        "content_sha": "sha-1",
        "raw_json": '{"id": "W1"}',
    }
    assert paper_repo.insert_raw_many(seeded, [record]) == 1
    assert paper_repo.insert_raw_many(seeded, [record]) == 0

    # 内容变了（sha 不同）→ 形成可审计的新版本
    changed = dict(record, content_sha="sha-2", raw_json='{"id": "W1", "v": 2}')
    assert paper_repo.insert_raw_many(seeded, [changed]) == 1


# --------------------------------------------------------------------------- #
# authors
# --------------------------------------------------------------------------- #
def test_author_link_keeps_position_order(seeded: Connection) -> None:
    author_repo.upsert_many(
        seeded,
        [
            Author(author_id="A1", name="Ada", name_norm="ada"),
            Author(author_id="A2", name="Bob", name_norm="bob"),
        ],
    )
    paper_repo.upsert_many(seeded, [make_paper("10.1000/a"), make_paper("10.1000/b")])
    author_repo.link_many(seeded, "10.1000/a", ["A2", "A1"])
    author_repo.link_many(seeded, "10.1000/a", ["A2", "A1"])  # 幂等

    links = author_repo.list_by_paper(seeded, "10.1000/a")
    assert [row[0] for row in links] == ["A2", "A1"]
    assert author_repo.count_links(seeded) == 2


# --------------------------------------------------------------------------- #
# citations / merges
# --------------------------------------------------------------------------- #
def test_citations_only_inside_corpus(seeded: Connection) -> None:
    paper_repo.upsert_many(seeded, [make_paper("10.1000/a"), make_paper("10.1000/b")])

    citation_repo.insert_ignore_many(seeded, [("10.1000/a", "10.1000/unknown")])
    assert citation_repo.count(seeded) == 0

    citation_repo.insert_ignore_many(seeded, [("10.1000/a", "10.1000/b")])
    citation_repo.insert_ignore_many(seeded, [("10.1000/a", "10.1000/b")])
    assert citation_repo.count(seeded) == 1

    assert [row[0] for row in citation_repo.cited_by(seeded, "10.1000/b")] == ["10.1000/a"]
    assert [row[0] for row in citation_repo.references_of(seeded, "10.1000/a")] == ["10.1000/b"]


def test_merge_relations_are_queryable(seeded: Connection) -> None:
    citation_repo.add_merges(seeded, [("10.1000/primary", "10.1000/dup", "fingerprint")])
    citation_repo.add_merges(seeded, [("10.1000/primary", "10.1000/dup", "fingerprint")])

    assert citation_repo.merged_ids(seeded, "10.1000/primary") == ["10.1000/dup"]
    assert citation_repo.primary_of(seeded, "10.1000/dup") == "10.1000/primary"
    assert citation_repo.count_merges(seeded) == 1


# --------------------------------------------------------------------------- #
# claims / reports
# --------------------------------------------------------------------------- #
def test_claims_are_idempotent_per_run(seeded: Connection) -> None:
    claim = Claim(text="Agents use tools", support=Support.UNSUPPORTED)
    assert claim_repo.insert_ignore_many(seeded, "run-0001", [claim]) == 1
    assert claim_repo.insert_ignore_many(seeded, "run-0001", [claim]) == 0
    assert claim_repo.count(seeded, "run-0001") == 1


def test_claim_citations_upsert_without_null_keys(seeded: Connection) -> None:
    claim = Claim(text="x", support=Support.SUPPORTED, citations=[Citation(paper_id="W1")])
    claim_repo.insert_ignore_many(seeded, "run-0001", [claim])
    claim_id = f"run-0001:{claim_repo.text_sha('x')[:12]}"

    claim_repo.insert_citations_many(seeded, claim_id, [("W1", None, "snip", 0.5)])
    claim_repo.insert_citations_many(seeded, claim_id, [("W1", None, "snip2", 0.9)])

    rows = seeded.execute(
        text("SELECT chunk_idx, snippet, score FROM claim_citations WHERE claim_id=:cid"),
        {"cid": claim_id},
    ).all()
    assert len(rows) == 1
    assert rows[0].chunk_idx == -1
    assert rows[0].snippet == "snip2"


def test_report_idempotency_and_drift(seeded: Connection) -> None:
    base = {
        "report_id": "rep-1",
        "topic_id": "ai-agents",
        "run_id": "run-0001",
        "content_md": "# weekly",
        "content_sha": "sha-a",
    }
    assert report_repo.insert_ignore(seeded, Report(**base)) == 1
    assert report_repo.insert_ignore(seeded, Report(**base)) == 0

    drifted = dict(base, report_id="rep-2", content_md="# weekly v2", content_sha="sha-b")
    assert report_repo.insert_ignore(seeded, Report(**drifted)) == 1
    assert len(report_repo.get_by_run(seeded, "run-0001")) == 2


# --------------------------------------------------------------------------- #
# run lifecycle / locks
# --------------------------------------------------------------------------- #
def test_single_running_run_per_topic(seeded: Connection) -> None:
    with pytest.raises(IntegrityError):
        run_repo.create(
            seeded,
            run_id="run-0002",
            topic_id="ai-agents",
            trigger="manual",
            state=RunState.RUNNING,
        )


def test_seq_allocation_advances_per_run(seeded: Connection) -> None:
    assert run_repo.allocate_seq(seeded, "run-0001") == 1
    assert run_repo.allocate_seq(seeded, "run-0001") == 2
    assert run_repo.get(seeded, "run-0001")._mapping["next_seq"] == 2


def test_lock_acquire_release_and_expiry(seeded: Connection) -> None:
    assert lock_repo.acquire(seeded, "ai-agents", "owner-a") is True
    assert lock_repo.acquire(seeded, "ai-agents", "owner-b") is False
    assert lock_repo.release(seeded, "ai-agents", "owner-a") is True
    assert lock_repo.acquire(seeded, "ai-agents", "owner-b") is True

    # 过期锁会被回收（用未来时间模拟）
    cleaned = lock_repo.cleanup_expired(seeded, now="2099-01-01T00:00:00Z")
    assert cleaned == ["ai-agents"]
    assert lock_repo.get(seeded, "ai-agents") is None


# --------------------------------------------------------------------------- #
# sync / llm cache
# --------------------------------------------------------------------------- #
def test_sync_cursor_roundtrip(seeded: Connection) -> None:
    sync_repo.set_cursor(seeded, "openalex", "sel-1", cursor="*", since="2026-01-01")
    row = sync_repo.get(seeded, "openalex", "sel-1")
    assert row._mapping["last_cursor"] == "*"
    assert row._mapping["last_since"] == "2026-01-01"
    assert row._mapping["status"] == "idle"


def test_llm_cache_never_overwrites_and_counts_hits(seeded: Connection) -> None:
    assert llm_repo.cache_put(seeded, "sha-x", model="deepseek-flash", response_json='{"a":1}') == 1
    assert llm_repo.cache_put(seeded, "sha-x", model="deepseek-flash", response_json='{"a":2}') == 0

    llm_repo.cache_hit(seeded, "sha-x")
    row = llm_repo.cache_get(seeded, "sha-x")._mapping
    assert row["response_json"] == '{"a":1}'
    assert row["hit_count"] == 1


def test_llm_call_summary(seeded: Connection) -> None:
    llm_repo.record(
        seeded,
        run_id="run-0001",
        agent="reporter",
        provider="deepseek",
        model="deepseek-flash",
        route_reason="cloud:default",
        request_sha="sha-1",
        req_tokens=100,
        resp_tokens=50,
        cost=0.0012,
    )
    llm_repo.record(
        seeded,
        run_id="run-0001",
        agent="reporter",
        provider="deepseek",
        model="deepseek-flash",
        route_reason="cloud:default",
        request_sha="sha-2",
        cost=0.0,
        cache_hit=True,
    )
    summary = llm_repo.summary_by_run(seeded, "run-0001")
    assert summary["calls"] == 2
    assert summary["cache_hits"] == 1
    assert summary["cost_usd"] == pytest.approx(0.0012)


def test_metrics_are_recomputable(seeded: Connection) -> None:
    insert = text(
        "INSERT INTO metrics(scope, scope_id, metric, value, ts) VALUES (:scope,:sid,:metric,:value,:ts)"
        " ON CONFLICT(scope, scope_id, metric) DO UPDATE SET value=excluded.value, ts=excluded.ts"
    )
    seeded.execute(
        insert,
        {
            "scope": "run",
            "sid": "run-0001",
            "metric": "grounding",
            "value": 0.5,
            "ts": "2026-01-01T00:00:00Z",
        },
    )
    seeded.execute(
        insert,
        {
            "scope": "run",
            "sid": "run-0001",
            "metric": "grounding",
            "value": 0.8,
            "ts": "2026-01-02T00:00:00Z",
        },
    )

    rows = seeded.execute(
        text(
            "SELECT value, COUNT(*) OVER () FROM metrics WHERE scope='run' AND scope_id='run-0001'"
        )
    ).all()
    assert len(rows) == 1
    assert rows[0][0] == pytest.approx(0.8)
