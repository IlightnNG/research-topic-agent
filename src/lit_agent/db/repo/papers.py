"""论文表仓储：**唯一写入口**，并实现 ADR-0005 §7.2 的 upsert 边界。

边界（重复抓取时不得越界）：
- 源字段：每次抓取可更新；
- 本地派生字段：`parse_status / n_chunks / merged_ids_json / paper_id` 只能由解析与去重写。
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_papers, t_papers_raw
from lit_agent.models.paper import Paper

__all__ = [
    "SOURCE_FIELDS",
    "count",
    "get",
    "insert_raw_many",
    "iter_all",
    "set_parse_status",
    "title_norm",
    "upsert_many",
]

#: 允许被"重新抓取"覆盖的列（其余列属本地派生，禁止由源适配器写入）
SOURCE_FIELDS: tuple[str, ...] = (
    "source",
    "source_id",
    "doi",
    "title",
    "title_norm",
    "abstract",
    "year",
    "published_at",
    "venue_id",
    "venue_name",
    "is_oa",
    "oa_pdf_url",
    "language",
    "cited_by_count",
    "source_updated_at",
    "row_updated_at",
)

_LEADING_ARTICLE = re.compile(r"^(a|an|the)\s+")
_NON_WORD = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def title_norm(title: str) -> str:
    """标题指纹：NFKC → 小写 → 去前导冠词 → 非字母数字折叠为空格 → 去首尾空白。

    注意：这是"去重指纹"，不是展示用标题；算法改动会使历史指纹不一致（需重算脚本）。
    """
    text = unicodedata.normalize("NFKC", title).strip().lower()
    text = _LEADING_ARTICLE.sub("", text)
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def _row(paper: Paper, *, now: str) -> dict[str, Any]:
    return {
        "paper_id": paper.paper_id,
        "source": paper.source,
        "source_id": paper.source_id or paper.paper_id,
        "doi": paper.paper_id if paper.paper_id.lower().startswith("10.") else None,
        "title": paper.title,
        "title_norm": title_norm(paper.title),
        "abstract": paper.abstract or None,
        "year": paper.year,
        "published_at": paper.published_at.isoformat() if paper.published_at else None,
        "venue_id": paper.venue_id,
        "venue_name": paper.venue,
        "is_oa": int(paper.is_oa),
        "oa_pdf_url": paper.oa_pdf_url,
        "language": paper.language,
        "parse_status": paper.parse_status.value,
        "n_chunks": 0,
        "cited_by_count": paper.cited_by_count,
        "merged_ids_json": json.dumps(sorted(paper.merged_ids), ensure_ascii=False),
        "source_updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
        "row_updated_at": now,
        "created_at": now,
    }


def upsert_many(conn: Connection, papers: Iterable[Paper], *, now: str | None = None) -> int:
    """幂等写入：只覆盖 `SOURCE_FIELDS`，派生字段保持原值。返回处理行数。"""
    stamp = now or utcnow_iso()
    rows = [_row(paper, now=stamp) for paper in papers]
    if not rows:
        return 0
    stmt = sqlite_insert(t_papers).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_papers.c.paper_id],
        set_={field: getattr(stmt.excluded, field) for field in SOURCE_FIELDS},
    )
    conn.execute(stmt)
    return len(rows)


def set_parse_status(
    conn: Connection, paper_id: str, status: str, *, n_chunks: int | None = None
) -> None:
    """解析阶段专用：只写派生字段 `parse_status / n_chunks`。"""
    values: dict[str, Any] = {"parse_status": status}
    if n_chunks is not None:
        values["n_chunks"] = n_chunks
    conn.execute(t_papers.update().where(t_papers.c.paper_id == paper_id).values(**values))


def set_merged_ids(conn: Connection, paper_id: str, merged_ids: Sequence[str]) -> None:
    """去重阶段专用：写 `merged_ids_json`（派生字段，源数据不得覆盖）。"""
    conn.execute(
        t_papers.update()
        .where(t_papers.c.paper_id == paper_id)
        .values(merged_ids_json=json.dumps(sorted(merged_ids), ensure_ascii=False))
    )


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_papers)).scalar_one())


def get(conn: Connection, paper_id: str) -> Any:
    return conn.execute(select(t_papers).where(t_papers.c.paper_id == paper_id)).first()


def iter_all(conn: Connection, *, limit: int | None = None) -> Sequence[Any]:
    stmt = select(t_papers).order_by(t_papers.c.paper_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return conn.execute(stmt).all()


def insert_raw_many(
    conn: Connection,
    records: Iterable[dict[str, Any]],
    *,
    now: str | None = None,
) -> int:
    """源记录原样入库：`(source, source_id, content_sha)` 冲突即忽略（ADR-0005 §7.1）。"""
    stamp = now or utcnow_iso()
    rows = [
        {
            "source": item["source"],
            "source_id": item["source_id"],
            "run_id": item.get("run_id"),
            "fetched_at": item.get("fetched_at", stamp),
            "content_sha": item["content_sha"],
            "raw_json": item["raw_json"],
        }
        for item in records
    ]
    if not rows:
        return 0
    stmt = (
        sqlite_insert(t_papers_raw)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=[
                t_papers_raw.c.source,
                t_papers_raw.c.source_id,
                t_papers_raw.c.content_sha,
            ]
        )
    )
    result = conn.execute(stmt)
    return int(result.rowcount or 0)
