"""解析编排：PDF（下载/抽取）→ 分块 → 写 `paper_chunks` 与 `parse_status`。

不变量
- 单篇失败不打断整轮（`parse_status='failed'` + 错误计数）；
- 写入顺序：先替换块，再改状态（同一事务）；
- 只处理 `parse_status in ('pending','failed')` 且有 `oa_pdf_url` 的论文。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.repo import chunks as chunk_repo
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import LitError
from lit_agent.parsing.chunking import chunk_text
from lit_agent.parsing.pdf import download_oa, extract_pdf_text
from lit_agent.stores.files import paper_path

__all__ = ["parse_papers"]


def _candidates(settings: Settings, limit: int | None) -> list[dict[str, Any]]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT paper_id, oa_pdf_url FROM papers"
                    " WHERE oa_pdf_url IS NOT NULL AND parse_status IN ('pending','failed')"
                    " ORDER BY paper_id" + (" LIMIT :limit" if limit else "")
                ),
                {"limit": limit} if limit else {},
            ).all()
    finally:
        engine.dispose()
    return [dict(row._mapping) for row in rows]


def parse_papers(
    settings: Settings,
    *,
    limit: int | None = None,
    token_budget: int = 400,
    client: Any | None = None,
) -> dict[str, Any]:
    """执行一轮解析，返回计数与错误样例。"""
    candidates = _candidates(settings, limit)
    ok = failed = skipped = total_chunks = 0
    errors: list[dict[str, str]] = []

    for row in candidates:
        paper_id = str(row["paper_id"])
        path = paper_path(settings, paper_id)
        try:
            if not path.exists():
                download_oa(settings, paper_id, str(row["oa_pdf_url"]), client=client)
            result = extract_pdf_text(path)
            if not result.ok:
                raise LitError(
                    "E_SRC_SCHEMA",
                    f"PDF 无可抽取文本：{result.error or 'empty'}",
                    context={"paper_id": paper_id},
                )
            pieces = chunk_text(result.text, budget_tokens=token_budget)
            if not pieces:
                raise LitError("E_SRC_SCHEMA", "分块结果为空", context={"paper_id": paper_id})

            engine = make_engine(settings)
            try:
                with connect(engine, immediate=True) as conn:
                    written = chunk_repo.replace_chunks(conn, paper_id, pieces)
                    paper_repo.set_parse_status(conn, paper_id, "ok", n_chunks=written)
            finally:
                engine.dispose()
            ok += 1
            total_chunks += len(pieces)
        except LitError as exc:
            engine = make_engine(settings)
            try:
                with connect(engine, immediate=True) as conn:
                    paper_repo.set_parse_status(conn, paper_id, "failed", n_chunks=0)
            finally:
                engine.dispose()
            failed += 1
            if len(errors) < 10:
                errors.append({"paper_id": paper_id, "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001 - 兜底：任何单篇异常都不许打断整轮
            failed += 1
            if len(errors) < 10:
                errors.append(
                    {"paper_id": paper_id, "code": "E_UNEXPECTED", "message": str(exc)[:200]}
                )

    return {
        "candidates": len(candidates),
        "ok": ok,
        "failed": failed,
        "skipped": skipped,
        "chunks": total_chunks,
        "errors": errors,
    }
