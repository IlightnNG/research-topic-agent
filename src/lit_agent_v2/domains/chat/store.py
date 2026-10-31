"""V2 chat session persistence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from lit_agent_v2.storage.db import Database

__all__ = ["ChatStore"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ChatStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, topic_id: str) -> str:
        session_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO chat_sessions(id,topic_id,created_at) VALUES (?,?,?)",
                (session_id, topic_id, _now()),
            )
        return session_id

    def append(self, session_id: str, role: str, content: str, citations: list[dict] | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages(id,session_id,role,content,citations_json,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    session_id,
                    role,
                    content,
                    json.dumps(citations or [], ensure_ascii=False),
                    _now(),
                ),
            )

    def history(self, session_id: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT role,content,citations_json,created_at FROM chat_messages"
                " WHERE session_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [
            {
                "role": row["role"],
                "content": row["content"],
                "citations": json.loads(row["citations_json"] or "[]"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
