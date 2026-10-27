"""PaperCard 缓存（3.2 / S2）：按 paper_id + content_sha 幂等存取。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

__all__ = ["get_card", "upsert_card"]


def get_card(conn: Connection, paper_id: str, content_sha: str, version: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            "SELECT card_json FROM paper_cards"
            " WHERE paper_id = :pid AND content_sha = :sha AND version = :ver"
        ),
        {"pid": paper_id, "sha": content_sha, "ver": version},
    ).first()
    if row is None:
        return None
    import json

    return json.loads(row[0])


def upsert_card(
    conn: Connection,
    *,
    paper_id: str,
    content_sha: str,
    version: int,
    card: dict[str, Any],
) -> None:
    import json

    now = datetime.now(UTC).isoformat()
    conn.execute(
        text(
            "INSERT INTO paper_cards (paper_id, content_sha, version, card_json, created_at)"
            " VALUES (:pid, :sha, :ver, :card, :ts)"
            " ON CONFLICT(paper_id) DO UPDATE SET"
            " content_sha = excluded.content_sha, version = excluded.version,"
            " card_json = excluded.card_json, created_at = excluded.created_at"
        ),
        {
            "pid": paper_id,
            "sha": content_sha,
            "ver": version,
            "card": json.dumps(card, ensure_ascii=False, sort_keys=True),
            "ts": now,
        },
    )
