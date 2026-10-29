"""论文详情（3.2 / S8）：Paper Tab 的最小数据源。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
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
            {"author_id": str(item[0]), "name": str(item[1])}
            for item in conn.execute(
                text(
                    "SELECT a.author_id, a.name FROM authors a"
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


@router.get("/{paper_id}/pdf")
def get_pdf(paper_id: str, request: Request, engine: Any = Depends(get_engine)) -> Response:
    """本地 PDF（支持 Range）；没有文件时 404，外部 URL 直接重定向。"""
    with connect(engine) as conn:
        row = conn.execute(
            text("SELECT COALESCE(pdf_path,''), COALESCE(pdf_url,'') FROM papers WHERE paper_id = :pid"),
            {"pid": paper_id},
        ).first()
    if row is None:
        raise LitError(E_NOT_FOUND, f"paper not found: {paper_id}", context={"paper_id": paper_id})
    path_raw, url = row
    if url:
        return RedirectResponse(str(url), status_code=307)
    path = Path(str(path_raw)) if path_raw else None
    if path is None or not path.is_file():
        raise LitError(
            E_NOT_FOUND,
            f"PDF not available for {paper_id}",
            context={"paper_id": paper_id},
        )

    size = path.stat().st_size
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", request.headers.get("range", "").strip())
    if match:
        start = int(match.group(1) or 0)
        end = int(match.group(2)) if match.group(2) else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{size}"},
            )
        chunk = path.read_bytes()[start : end + 1]
        return Response(
            content=chunk,
            status_code=206,
            media_type="application/pdf",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Content-Length": str(len(chunk)),
            },
        )
    return FileResponse(path, media_type="application/pdf", filename=path.name)
