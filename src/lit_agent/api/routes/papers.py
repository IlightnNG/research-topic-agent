"""论文详情（3.2 / S8）：Paper Tab 的最小数据源。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine
from lit_agent.db.session import connect
from lit_agent.errors import E_NOT_FOUND, LitError

router = APIRouter()


@router.get("/{paper_id}")
def get_paper(paper_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            text(
                "SELECT paper_id, title, COALESCE(abstract,''), COALESCE(source,''), year,"
                " COALESCE(pdf_path,''), COALESCE(pdf_url,'')"
                " FROM papers WHERE paper_id = :pid"
            ),
            {"pid": paper_id},
        ).first()
        if row is None:
            raise LitError(E_NOT_FOUND, f"paper 不存在：{paper_id}", context={"paper_id": paper_id})
        authors = [
            str(item[0])
            for item in conn.execute(
                text(
                    "SELECT a.name FROM authors a"
                    " JOIN paper_authors pa ON pa.author_id = a.author_id"
                    " WHERE pa.paper_id = :pid ORDER BY pa.position"
                ),
                {"pid": paper_id},
            ).all()
        ]
        claims = [
            {
                "claim_id": item[0],
                "text": item[1],
                "snippet": item[2] or "",
            }
            for item in conn.execute(
                text(
                    "SELECT c.claim_id, c.text, cc.snippet"
                    " FROM claim_citations cc JOIN claims c ON c.claim_id = cc.claim_id"
                    " WHERE cc.paper_id = :pid ORDER BY c.created_at"
                ),
                {"pid": paper_id},
            ).all()
        ]
    return {
        "paper_id": row[0],
        "title": row[1],
        "abstract": row[2],
        "source": row[3],
        "year": row[4],
        "pdf_path": row[5] or None,
        "pdf_url": row[6] or None,
        "pdf_available": bool(row[5] or row[6]),
        "authors": authors,
        "claims": claims,
    }
