"""派生物重建与对账（执行 guide §2 的不变量："SQLite 是唯一真相源"）。

`rebuild_*` 只从 SQLite 读、只往派生物写；`verify_counts` 做三方对账：
`sqlite.papers == kuzu.papers == qdrant.points`（作者/引用/著作关系同理）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.base import utcnow_iso
from lit_agent.db.session import connect, make_engine, write_store_identity
from lit_agent.selftest import assert_ascii_path, read_store_meta
from lit_agent.stores import graph as graph_store
from lit_agent.stores import vector as vector_store
from lit_agent.stores.vector import get_client

__all__ = ["rebuild_graph", "rebuild_vector", "verify_counts"]


def _load_papers(settings: Settings) -> list[dict[str, Any]]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT paper_id, title, abstract, year, source, venue_id,"
                    " published_at, row_updated_at FROM papers"
                    " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)"
                    " ORDER BY paper_id"
                )
            ).all()
    finally:
        engine.dispose()
    return [dict(row._mapping) for row in rows]


def _load_authorships(
    settings: Settings,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, int]]]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            authors = [
                dict(row._mapping)
                for row in conn.execute(
                    text("SELECT author_id, name, name_norm FROM authors ORDER BY author_id")
                ).all()
            ]
            links = [
                (str(row[0]), str(row[1]), int(row[2]))
                for row in conn.execute(
                    text(
                        "SELECT paper_id, author_id, position FROM paper_authors"
                        " ORDER BY paper_id, position"
                    )
                ).all()
            ]
    finally:
        engine.dispose()
    return authors, links


def _load_citations(settings: Settings) -> list[tuple[str, str]]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(text("SELECT citing_id, cited_id FROM citations")).all()
    finally:
        engine.dispose()
    return [(str(row[0]), str(row[1])) for row in rows]


def _schema_version() -> str:
    from lit_agent.structure import SCHEMA_VERSION

    return SCHEMA_VERSION


def rebuild_graph(settings: Settings) -> dict[str, Any]:
    """从 SQLite 全量重建 Kuzu 图（幂等：MERGE）。"""
    papers = _load_papers(settings)
    authors, links = _load_authorships(settings)
    citations = _load_citations(settings)
    # 稳定时间戳：同一份数据重复重建必须得到同一个值，否则关系 MERGE 会重复建边
    epoch = max(
        (row["row_updated_at"] for row in papers if row.get("row_updated_at")), default=None
    )
    first_seen = epoch or utcnow_iso()

    with graph_store.GraphStore.open(settings) as store:
        written_papers = store.upsert_papers(
            [
                {
                    "paper_id": row["paper_id"],
                    "title": row["title"],
                    "year": row["year"],
                    "source": row["source"],
                    "venue_id": row["venue_id"],
                    "discovered_at": row["row_updated_at"] or first_seen,
                }
                for row in papers
            ]
        )
        written_authors = store.upsert_authors(authors)
        store.upsert_authorships(links)
        written_citations = store.upsert_citations(citations, first_seen=first_seen)
        counts = store.counts()
        size_mb = round(
            sum(
                item.stat().st_size
                for item in store.path.parent.glob(f"{store.path.name}*")
                if item.is_file()
            )
            / (1024 * 1024),
            3,
        )

    write_store_identity(
        settings, "kuzu", schema_version=_schema_version(), extra={"counts": counts}
    )
    return {
        "written": {
            "papers": written_papers,
            "authors": written_authors,
            "citations": written_citations,
            "authorships": len(links),
        },
        "counts": counts,
        "size_mb_after_close": size_mb,
    }


def rebuild_vector(settings: Settings, *, embedder: Any | None = None) -> dict[str, Any]:
    """从 SQLite 全量重建 Qdrant collection（幂等：point id 由 paper_id 派生）。"""
    rows = _load_papers(settings)
    store = vector_store.VectorStore.open(settings, embedder)
    written = store.upsert_papers(rows)
    count = store.count()
    identity = vector_store.identity_fields(store.embedder, store.collection)
    write_store_identity(settings, "qdrant", schema_version=_schema_version(), **identity)
    return {"written": written, "points": count, "collection": store.collection, **identity}


def verify_counts(settings: Settings, *, embedder: Any | None = None) -> dict[str, Any]:
    """三方对账：SQLite（真相源） vs Kuzu vs Qdrant。"""
    papers = _load_papers(settings)
    authors, links = _load_authorships(settings)
    citations = _load_citations(settings)

    with graph_store.GraphStore.open(settings) as store:
        graph_counts = store.counts()

    # 对账前先确认向量库**真的存在**：`VectorStore.open()` 会自动建空 collection，
    # 直接用它会把"向量库丢失"判成 ok（假绿）。这里先查 collection 是否在。
    meta = read_store_meta(settings.storage.sqlite_file).get("qdrant") or {}
    active = str(meta.get("active_collection") or settings.vector.active_collection)
    existing = {
        item.name
        for item in get_client(
            assert_ascii_path(settings.storage.qdrant_dir, label="storage.qdrant_path")
        )
        .get_collections()
        .collections
    }
    if active not in existing:
        return {
            "ok": False,
            "sqlite": {
                "papers": len(papers),
                "authors": len(authors),
                "citations": len(citations),
                "authorships": len(links),
            },
            "graph": graph_counts,
            "qdrant": {"points": None, "collection": active},
            "mismatches": [f"qdrant: collection {active!r} 缺失（SQLite 有数据但向量库没了）"],
        }

    vector_count = vector_store.VectorStore.open(settings, embedder).count()

    expected = {
        "papers": len(papers),
        "authors": len(authors),
        "citations": len(citations),
        "authorships": len(links),
    }
    mismatches: list[str] = []
    for key in ("papers", "authors", "citations", "authorships"):
        if graph_counts.get(key, -1) != expected[key]:
            mismatches.append(
                f"graph.{key}={graph_counts.get(key)} != sqlite.{key}={expected[key]}"
            )
    if vector_count != expected["papers"]:
        mismatches.append(f"qdrant.points={vector_count} != sqlite.papers={expected['papers']}")

    return {
        "ok": not mismatches,
        "sqlite": expected,
        "graph": graph_counts,
        "qdrant": {"points": vector_count},
        "mismatches": mismatches,
    }
