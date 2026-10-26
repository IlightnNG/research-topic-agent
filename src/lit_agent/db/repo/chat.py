"""Chat 会话/消息仓库（3.3）。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from lit_agent.errors import E_NOT_FOUND, LitError

__all__ = ["append_message", "create_session", "latest_session", "list_messages", "list_sessions"]


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def create_session(conn: Connection, topic_id: str) -> str:
    session_id = f"chat-{uuid.uuid4().hex[:12]}"
    conn.execute(
        text(
            "INSERT INTO chat_sessions (id, topic_id, created_at)"
            " VALUES (:id, :topic, :ts)"
        ),
        {"id": session_id, "topic": topic_id, "ts": _now()},
    )
    return session_id


def _session_row(row: Any) -> dict[str, Any]:
    preview = str(row[4] or "").strip()
    return {
        "id": row[0],
        "topic_id": row[1],
        "created_at": row[2],
        "last_message_at": row[3],
        "preview": preview[:40],
    }


_SESSION_SQL = (
    "SELECT s.id, s.topic_id, s.created_at,"
    " (SELECT MAX(m.ts) FROM chat_messages m WHERE m.session_id = s.id) AS last_message_at,"
    " (SELECT m.content FROM chat_messages m"
    "  WHERE m.session_id = s.id AND m.role = 'user' ORDER BY m.ts ASC LIMIT 1) AS preview"
    " FROM chat_sessions s"
)


def latest_session(conn: Connection, topic_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(_SESSION_SQL + " WHERE s.topic_id = :topic"
             " ORDER BY COALESCE(last_message_at, s.created_at) DESC LIMIT 1"),
        {"topic": topic_id},
    ).first()
    return _session_row(row) if row else None


def list_sessions(conn: Connection, topic_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            _SESSION_SQL + " WHERE s.topic_id = :topic"
            " ORDER BY COALESCE(last_message_at, s.created_at) DESC LIMIT :limit"
        ),
        {"topic": topic_id, "limit": limit},
    ).all()
    return [_session_row(row) for row in rows]


def append_message(
    conn: Connection,
    *,
    session_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
    trace: list[dict[str, Any]] | None = None,
    reason_code: str | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    exists = conn.execute(
        text("SELECT 1 FROM chat_sessions WHERE id = :id"), {"id": session_id}
    ).first()
    if exists is None:
        raise LitError(E_NOT_FOUND, f"会话不存在：{session_id}", context={"session_id": session_id})
    message_id = f"msg-{uuid.uuid4().hex[:12]}"
    stamp = ts or _now()
    conn.execute(
        text(
            "INSERT INTO chat_messages"
            " (id, session_id, role, content, citations_json, trace_json, reason_code, ts)"
            " VALUES (:id, :sid, :role, :content, :citations, :trace, :reason, :ts)"
        ),
        {
            "id": message_id,
            "sid": session_id,
            "role": role,
            "content": content,
            "citations": json.dumps(citations or [], ensure_ascii=False),
            "trace": json.dumps(trace or [], ensure_ascii=False),
            "reason": reason_code,
            "ts": stamp,
        },
    )
    return {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "citations": citations or [],
        "trace": trace or [],
        "reason_code": reason_code,
        "ts": stamp,
    }


def list_messages(conn: Connection, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT id, role, content, citations_json, trace_json, reason_code, ts FROM chat_messages"
            " WHERE session_id = :sid ORDER BY ts ASC LIMIT :limit"
        ),
        {"sid": session_id, "limit": limit},
    ).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "citations": json.loads(row[3] or "[]"),
                "trace": json.loads(row[4] or "[]"),
                "reason_code": row[5],
                "ts": row[6],
            }
        )
    return out
