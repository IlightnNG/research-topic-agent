"""断言（claim）与"断言-证据"仓储。

两条不可协商的规则：
1. **不可落地的 claim 也要入库**（`support='unsupported'`）——丢弃会伪造 grounding=100%；
2. `(run_id, text_sha)` 幂等：同一 run 重放不重复计数。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_claim_citations, t_claims
from lit_agent.models.claim import Claim

__all__ = [
    "claim_id_for",
    "count",
    "insert_citations_many",
    "insert_ignore_many",
    "list_by_run",
    "text_sha",
]


def text_sha(text: str) -> str:
    """规范化文本哈希（去首尾空白 + 折叠内部空白），作为 claim 的幂等键。"""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def claim_id_for(run_id: str, digits: str) -> str:
    """`<run_id>:<sha 前 12 位>`：可读、可回查、天然唯一。"""
    return f"{run_id}:{digits[:12]}"


def insert_ignore_many(
    conn: Connection,
    run_id: str,
    claims: Iterable[Claim],
    *,
    report_id: str | None = None,
    now: str | None = None,
) -> int:
    stamp = now or utcnow_iso()
    rows: list[dict[str, Any]] = []
    for claim in claims:
        digest = claim.text_sha or text_sha(claim.text)
        rows.append(
            {
                "claim_id": claim.claim_id or claim_id_for(run_id, digest),
                "run_id": run_id,
                "report_id": report_id or claim.report_id,
                "text": claim.text,
                "text_sha": digest,
                "support": claim.support.value,
                "created_at": stamp,
            }
        )
    if not rows:
        return 0
    stmt = (
        sqlite_insert(t_claims)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[t_claims.c.run_id, t_claims.c.text_sha])
    )
    result = conn.execute(stmt)
    return int(result.rowcount or 0)


def insert_citations_many(
    conn: Connection,
    claim_id: str,
    items: Iterable[tuple[str, int | None, str | None, float | None]],
) -> int:
    """`(paper_id, chunk_idx, snippet, score)`；`chunk_idx=None` 归一化为 -1（避免 NULL 破坏唯一索引）。"""
    rows = [
        {
            "claim_id": claim_id,
            "paper_id": paper_id,
            "chunk_idx": -1 if chunk_idx is None else chunk_idx,
            "snippet": snippet,
            "score": score,
        }
        for paper_id, chunk_idx, snippet, score in items
    ]
    if not rows:
        return 0
    stmt = sqlite_insert(t_claim_citations).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            t_claim_citations.c.claim_id,
            t_claim_citations.c.paper_id,
            t_claim_citations.c.chunk_idx,
        ],
        set_={"snippet": stmt.excluded.snippet, "score": stmt.excluded.score},
    )
    conn.execute(stmt)
    return len(rows)


def attach_report(conn: Connection, run_id: str, report_id: str) -> None:
    """报告写完后回填 `claims.report_id`（同事务）。"""
    conn.execute(t_claims.update().where(t_claims.c.run_id == run_id).values(report_id=report_id))


def list_by_run(conn: Connection, run_id: str) -> Sequence[Any]:
    stmt = select(t_claims).where(t_claims.c.run_id == run_id).order_by(t_claims.c.claim_id)
    return conn.execute(stmt).all()


def count(conn: Connection, run_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(t_claims)
    if run_id is not None:
        stmt = stmt.where(t_claims.c.run_id == run_id)
    return int(conn.execute(stmt).scalar_one())
