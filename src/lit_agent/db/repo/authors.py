"""作者与"论文-作者"关系仓储。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_authors, t_paper_authors
from lit_agent.models.author import Author

__all__ = ["count", "count_links", "link_many", "list_by_paper", "upsert_many"]


def upsert_many(conn: Connection, authors: Iterable[Author], *, now: str | None = None) -> int:
    stamp = now or utcnow_iso()
    rows = [
        {
            "author_id": author.author_id,
            "name": author.name,
            "name_norm": author.name_norm,
            "row_updated_at": stamp,
        }
        for author in authors
    ]
    if not rows:
        return 0
    stmt = sqlite_insert(t_authors).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_authors.c.author_id],
        set_={
            "name": stmt.excluded.name,
            "name_norm": stmt.excluded.name_norm,
            "row_updated_at": stmt.excluded.row_updated_at,
        },
    )
    conn.execute(stmt)
    return len(rows)


def link_many(
    conn: Connection,
    paper_id: str,
    author_ids: Iterable[str],
    *,
    corresponding: str | None = None,
) -> int:
    """幂等建立 `(paper_id, position)` 关系；位置保留作者顺序。"""
    rows = [
        {
            "paper_id": paper_id,
            "author_id": author_id,
            "position": position,
            "is_corresponding": int(author_id == corresponding),
        }
        for position, author_id in enumerate(author_ids)
    ]
    if not rows:
        return 0
    stmt = sqlite_insert(t_paper_authors).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_paper_authors.c.paper_id, t_paper_authors.c.position],
        set_={
            "author_id": stmt.excluded.author_id,
            "is_corresponding": stmt.excluded.is_corresponding,
        },
    )
    conn.execute(stmt)
    return len(rows)


def list_by_paper(conn: Connection, paper_id: str) -> Sequence[Any]:
    stmt = (
        select(t_paper_authors.c.author_id, t_paper_authors.c.position)
        .where(t_paper_authors.c.paper_id == paper_id)
        .order_by(t_paper_authors.c.position)
    )
    return conn.execute(stmt).all()


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_authors)).scalar_one())


def count_links(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_paper_authors)).scalar_one())
