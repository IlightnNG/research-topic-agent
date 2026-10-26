"""Chat 路由（3.3）：会话 + 同步回答（L3）。

本轮不做 token 级 SSE：回答是确定性、毫秒级；前端可用 AbortController 中止（偏差 3.3-c）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text

from lit_agent.agents.chat import answer
from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.config import Settings
from lit_agent.db.repo import chat as chat_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_NOT_FOUND, LitError

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


def _ensure_topic(conn: Any, topic_id: str) -> None:
    row = conn.execute(text("SELECT 1 FROM topics WHERE id = :id"), {"id": topic_id}).first()
    if row is None:
        raise LitError(E_NOT_FOUND, f"topic 不存在：{topic_id}", context={"topic_id": topic_id})


@router.post("/{topic_id}/chat/sessions")
def create_chat_session(
    topic_id: str,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine, immediate=True) as conn:
        _ensure_topic(conn, topic_id)
        session_id = chat_repo.create_session(conn, topic_id)
    return {"topic_id": topic_id, "session_id": session_id}


@router.get("/{topic_id}/chat")
def get_chat(
    topic_id: str,
    session_id: str | None = None,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine) as conn:
        _ensure_topic(conn, topic_id)
        sessions = chat_repo.list_sessions(conn, topic_id)
        if session_id is None:
            current = chat_repo.latest_session(conn, topic_id)
        else:
            current = next((item for item in sessions if item["id"] == session_id), None)
            if current is None:
                raise LitError(E_NOT_FOUND, f"会话不存在：{session_id}")
        messages = chat_repo.list_messages(conn, current["id"]) if current else []
    return {"topic_id": topic_id, "sessions": sessions, "session": current, "messages": messages}


@router.post("/{topic_id}/chat")
def post_chat(
    topic_id: str,
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine, immediate=True) as conn:
        _ensure_topic(conn, topic_id)
        sessions = chat_repo.list_sessions(conn, topic_id)
        if body.session_id is not None:
            session = next((item for item in sessions if item["id"] == body.session_id), None)
            if session is None:
                raise LitError(E_NOT_FOUND, f"会话不存在：{body.session_id}")
        else:
            session = sessions[0] if sessions else {"id": chat_repo.create_session(conn, topic_id)}
        history = chat_repo.list_messages(conn, session["id"])
        chat_repo.append_message(conn, session_id=session["id"], role="user", content=body.message)

    reply = answer(settings, topic_id=topic_id, message=body.message, history=history)

    with connect(engine, immediate=True) as conn:
        assistant = chat_repo.append_message(
            conn,
            session_id=session["id"],
            role="assistant",
            content=reply.text,
            citations=reply.citations,
            trace=reply.trace,
            reason_code=reply.reason or None,
        )
    return {
        "topic_id": topic_id,
        "session_id": session["id"],
        "message": assistant,
        "answered": reply.answered,
        "reason": reply.reason,
    }
