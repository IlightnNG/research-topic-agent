"""SQLite 真相源单测（Phase 0 step 5.4 验收：重复运行计数不变；schema 守卫）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from lit_agent_min.models import Author, Citation, Claim, Paper, Support
from lit_agent_min.stores import SqliteStore, StoreSchemaError, verify_counts


def _paper(paper_id: str, refs: list[str] | None = None) -> Paper:
    return Paper(
        paper_id=paper_id,
        title=f"Title {paper_id}",
        abstract="abstract text",
        authors=[Author(author_id="A1", name="Ada", name_norm="ada")],
        year=2026,
        source="openalex",
        references=refs or [],
    )


def test_upsert_is_idempotent(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    papers = [_paper("10.1/a", ["10.1/b"]), _paper("10.1/b")]
    first = store.upsert_papers(papers, run_id="r1")
    before = store.counts()
    second = store.upsert_papers(papers, run_id="r2")
    after = store.counts()
    assert first == second
    assert before.as_dict() == after.as_dict()  # 重复写入零增长
    store.close()


def test_paper_id_set_reflects_upsert(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    store.upsert_papers([_paper("10.1/a")], run_id="r1")
    assert store.paper_ids() == {"10.1/a"}
    store.upsert_papers([_paper("10.1/b")], run_id="r1")
    assert store.paper_ids() == {"10.1/a", "10.1/b"}
    store.close()


def test_update_overwrites_changed_fields(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    store.upsert_papers([_paper("10.1/a")], run_id="r1")
    updated = _paper("10.1/a").model_copy(update={"title": "New Title"})
    store.upsert_papers([updated], run_id="r2")
    title = store.conn.execute("SELECT title FROM papers WHERE paper_id='10.1/a'").fetchone()[0]
    assert title == "New Title"
    store.close()


def test_only_in_corpus_references_become_edges(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    # 引用边只在本批语料内建立（避免悬挂边）；"W-unknown" 指向语料外 → 丢弃
    store.upsert_papers([_paper("10.1/a", ["10.1/b", "W-unknown"]), _paper("10.1/b")], run_id="r1")
    counts = store.counts()
    assert counts.papers == 2
    assert counts.citations == 1
    assert store.citation_count_for("10.1/b") == 1
    store.close()


def test_sync_state_roundtrip(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    assert store.get_cursor("openalex:T1") is None
    store.set_cursor("openalex:T1", cursor="c1", run_id="r1", items_seen=24)
    cursor = store.get_cursor("openalex:T1")
    assert cursor and cursor["cursor"] == "c1" and cursor["items_seen"] == 24
    store.close()


def test_claims_upsert_and_count(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "s.db")
    claims = [
        Claim(
            text="c1",
            citations=[Citation(paper_id="10.1/a", snippet="s")],
            support=Support.SUPPORTED,
        ),
        Claim(text="c2", citations=[Citation(paper_id="10.1/b")], support=Support.SUPPORTED),
    ]
    store.upsert_claims("r1", claims)
    assert store.counts().claims == 2
    store.upsert_claims("r1", claims)  # 同 run 重写不增长
    assert store.counts().claims == 2
    store.close()


def test_schema_guard_rejects_foreign_table(tmp_path: Path) -> None:
    """模拟 S3 spike 写入的旧结构：必须报错而不是静默写坏。"""
    import sqlite3

    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE papers(paper_id TEXT PRIMARY KEY, title TEXT);")
    conn.commit()
    conn.close()
    with pytest.raises(StoreSchemaError) as exc:
        SqliteStore(path)
    assert "缺少列" in str(exc.value)


def test_reset_true_rebuilds_schema(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("CREATE TABLE papers(paper_id TEXT PRIMARY KEY, title TEXT);")
    conn.commit()
    conn.close()
    store = SqliteStore(path, reset=True)
    assert store.is_empty()
    store.upsert_papers([_paper("10.1/a")], run_id="r1")
    assert store.counts().papers == 1
    store.close()


def test_verify_counts_reports_mismatches() -> None:
    assert verify_counts({"papers": 3}, {"papers": 3}) == {}
    assert verify_counts({"papers": 3}, {"papers": 2}) == {"papers": {"expected": 3, "actual": 2}}
    assert verify_counts({"papers": 3}, {}) == {"papers": {"expected": 3, "actual": -1}}
