"""作者面板（3.2 / S11）：paper–author 简化关系，不引入团队/图谱。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine
from lit_agent.db.session import connect
from lit_agent.errors import E_NOT_FOUND, LitError

router = APIRouter()


@router.get("/{author_id}")
def get_author(author_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            text(
                "SELECT author_id, name, COALESCE(orcid,''), COALESCE(last_institution,''),"
                " COALESCE(works_count,0) FROM authors WHERE author_id = :aid"
            ),
            {"aid": author_id},
        ).first()
        if row is None:
            raise LitError(E_NOT_FOUND, f"author not found: {author_id}", context={"author_id": author_id})

        papers = [
            {"paper_id": item[0], "title": item[1], "year": item[2], "source": item[3] or ""}
            for item in conn.execute(
                text(
                    "SELECT p.paper_id, p.title, p.year, COALESCE(p.source,'')"
                    " FROM papers p JOIN paper_authors pa ON pa.paper_id = p.paper_id"
                    " WHERE pa.author_id = :aid ORDER BY p.year DESC, p.paper_id LIMIT 20"
                ),
                {"aid": author_id},
            ).all()
        ]
        coauthors = [
            {"author_id": item[0], "name": item[1], "shared_papers": int(item[2])}
            for item in conn.execute(
                text(
                    "SELECT a2.author_id, a2.name, COUNT(*)"
                    " FROM paper_authors pa1"
                    " JOIN paper_authors pa2 ON pa2.paper_id = pa1.paper_id"
                    " AND pa2.author_id <> pa1.author_id"
                    " JOIN authors a2 ON a2.author_id = pa2.author_id"
                    " WHERE pa1.author_id = :aid"
                    " GROUP BY a2.author_id, a2.name"
                    " ORDER BY COUNT(*) DESC, a2.name LIMIT 10"
                ),
                {"aid": author_id},
            ).all()
        ]
    return {
        "author_id": row[0],
        "name": row[1],
        "orcid": row[2] or None,
        "institution": row[3] or None,
        "works_count": int(row[4] or 0),
        "papers": papers,
        "coauthors": coauthors,
    }
