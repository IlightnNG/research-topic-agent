"""引用边与去重合并关系仓储。

引用只保留"两端都在语料内"的边（guide §2.5 口径）：插入时用 `WHERE EXISTS` 过滤，
而不是事后 `DELETE`——避免把 FK 违例变成运行期异常。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_citations, t_paper_merges

__all__ = [
    "add_merges",
    "cited_by",
    "count",
    "count_merges",
    "insert_ignore_many",
    "merged_ids",
    "primary_of",
    "references_of",
]

_INSERT_EDGE = text(
    """
    INSERT OR IGNORE INTO citations (citing_id, cited_id, source, first_seen_at, run_id)
    SELECT :citing_id, :cited_id, :source, :first_seen_at, :run_id
    WHERE EXISTS (SELECT 1 FROM papers WHERE paper_id = :citing_id)
      AND EXISTS (SELECT 1 FROM papers WHERE paper_id = :cited_id)
    """
)


def insert_ignore_many(
    conn: Connection,
    pairs: Iterable[tuple[str, str]],
    *,
    source: str = "openalex",
    run_id: str | None = None,
    now: str | None = None,
) -> int:
    """批量写引用边（`(citing_id, cited_id)` 冲突即忽略）。返回实际尝试条数。"""
    stamp = now or utcnow_iso()
    rows = [
        {
            "citing_id": citing,
            "cited_id": cited,
            "source": source,
            "first_seen_at": stamp,
            "run_id": run_id,
        }
        for citing, cited in pairs
        if citing and cited and citing != cited
    ]
    if not rows:
        return 0
    conn.execute(_INSERT_EDGE, rows)
    return len(rows)


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_citations)).scalar_one())


def cited_by(conn: Connection, paper_id: str, *, limit: int = 50) -> Sequence[Any]:
    """谁引用了这篇（走 `ix_citations_cited`）。"""
    stmt = select(t_citations.c.citing_id).where(t_citations.c.cited_id == paper_id).limit(limit)
    return conn.execute(stmt).all()


def references_of(conn: Connection, paper_id: str, *, limit: int = 200) -> Sequence[Any]:
    stmt = select(t_citations.c.cited_id).where(t_citations.c.citing_id == paper_id).limit(limit)
    return conn.execute(stmt).all()


def add_merges(
    conn: Connection,
    merges: Iterable[tuple[str, str, str]],
    *,
    run_id: str | None = None,
    now: str | None = None,
) -> int:
    """`(primary_id, merged_id, reason)`；冲突即忽略（同一对只记一次）。"""
    stamp = now or utcnow_iso()
    rows = [
        {
            "primary_id": primary,
            "merged_id": merged,
            "run_id": run_id,
            "reason": reason,
            "created_at": stamp,
        }
        for primary, merged, reason in merges
        if primary and merged and primary != merged
    ]
    if not rows:
        return 0
    stmt = (
        sqlite_insert(t_paper_merges)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=[t_paper_merges.c.primary_id, t_paper_merges.c.merged_id]
        )
    )
    conn.execute(stmt)
    return len(rows)


def merged_ids(conn: Connection, primary_id: str) -> list[str]:
    stmt = select(t_paper_merges.c.merged_id).where(t_paper_merges.c.primary_id == primary_id)
    return [str(row[0]) for row in conn.execute(stmt).all()]


def primary_of(conn: Connection, merged_id: str) -> str | None:
    stmt = select(t_paper_merges.c.primary_id).where(t_paper_merges.c.merged_id == merged_id)
    row = conn.execute(stmt).first()
    return str(row[0]) if row else None


def count_merges(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_paper_merges)).scalar_one())
