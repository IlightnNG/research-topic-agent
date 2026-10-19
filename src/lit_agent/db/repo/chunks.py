"""分块仓储（`paper_chunks`）：一篇论文的块集合"整体替换"，避免残留孤儿块。"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection

from lit_agent.db.tables import t_paper_chunks
from lit_agent.parsing.chunking import Chunk

__all__ = ["count", "list_by_paper", "replace_chunks"]


def replace_chunks(
    conn: Connection, paper_id: str, chunks: Sequence[Chunk], *, section: str | None = None
) -> int:
    """同一事务内：先删该论文旧块，再插入新块（幂等）。"""
    conn.execute(delete(t_paper_chunks).where(t_paper_chunks.c.paper_id == paper_id))
    rows: list[dict[str, Any]] = [
        {
            "paper_id": paper_id,
            "chunk_idx": chunk.index,
            "section": section,
            "text_sha": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            "token_count": chunk.tokens,
            "page_from": None,
            "page_to": None,
            "char_start": None,
            "char_end": None,
        }
        for chunk in chunks
    ]
    if not rows:
        return 0
    conn.execute(t_paper_chunks.insert(), rows)
    return len(rows)


def list_by_paper(conn: Connection, paper_id: str) -> Sequence[Any]:
    stmt = (
        select(t_paper_chunks)
        .where(t_paper_chunks.c.paper_id == paper_id)
        .order_by(t_paper_chunks.c.chunk_idx)
    )
    return conn.execute(stmt).all()


def count(conn: Connection, paper_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(t_paper_chunks)
    if paper_id is not None:
        stmt = stmt.where(t_paper_chunks.c.paper_id == paper_id)
    return int(conn.execute(stmt).scalar_one())
