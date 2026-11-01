"""HTTP interface for topics, platform runs and conversations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lit_agent_v2.composition import build_chat_service
from lit_agent_v2.domains.chat.store import ChatStore
from lit_agent_v2.storage.db import Database
from lit_agent_v2.storage.report_store import ReportStore

from .runs import PlatformRunService
from .topics import TopicStore

__all__ = ["build_platform_router"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class TopicCreateBody(BaseModel):
    direction: str
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class RunCreateBody(BaseModel):
    focus_hint: str | None = None
    language: str = "en"
    limit: int = 40


class MessageBody(BaseModel):
    content: str


def build_platform_router(
    db: Database,
    *,
    corpus_root: Path,
    llm: Any | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v2")
    topics = TopicStore(db)
    runs = PlatformRunService(db, corpus_root=corpus_root, llm=llm)
    chat_store = ChatStore(db)
    reports = ReportStore(db)

    @router.get("/topics")
    def list_topics() -> list[dict[str, Any]]:
        return topics.list()

    @router.post("/topics", status_code=201)
    def create_topic(body: TopicCreateBody) -> dict[str, Any]:
        if not body.direction.strip():
            raise HTTPException(status_code=422, detail="E_INVALID_REQUEST")
        return topics.create(
            direction=body.direction,
            description=body.description,
            keywords=body.keywords,
            exclusions=body.exclusions,
            constraints=body.constraints,
        )

    @router.get("/topics/{topic_id}")
    def get_topic(topic_id: str) -> dict[str, Any]:
        topic = topics.get(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="E_TOPIC_NOT_FOUND")
        return topic

    @router.get("/topics/{topic_id}/brief")
    def get_brief(topic_id: str) -> dict[str, Any]:
        brief = topics.brief(topic_id)
        if brief is None:
            raise HTTPException(status_code=404, detail="E_TOPIC_NOT_FOUND")
        return brief

    @router.post("/topics/{topic_id}/normalize")
    def normalize_topic(topic_id: str) -> dict[str, Any]:
        brief = topics.brief(topic_id)
        if brief is None:
            raise HTTPException(status_code=404, detail="E_TOPIC_NOT_FOUND")
        return brief

    @router.get("/topics/{topic_id}/runs")
    def list_runs(topic_id: str) -> list[dict[str, Any]]:
        return runs.list_runs(topic_id)

    @router.post("/topics/{topic_id}/runs", status_code=202)
    def create_run(topic_id: str, body: RunCreateBody) -> dict[str, Any]:
        if body.language not in {"en", "zh"}:
            raise HTTPException(status_code=422, detail="E_INVALID_LANGUAGE")
        try:
            return runs.create(
                topic_id=topic_id,
                focus_hint=body.focus_hint,
                language=body.language,
                limit=body.limit,
            )
        except ValueError as exc:
            code = str(exc)
            status = 404 if code == "E_TOPIC_NOT_FOUND" else 422
            raise HTTPException(status_code=status, detail=code) from exc

    @router.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        return run

    @router.get("/runs/{run_id}/trace")
    def get_trace(run_id: str) -> dict[str, Any]:
        if runs.get(run_id) is None:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        return runs.trace(run_id)

    @router.post("/runs/{run_id}/pause")
    def pause_run(run_id: str) -> dict[str, Any]:
        run = runs.pause(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        return run

    @router.post("/runs/{run_id}/resume")
    def resume_run(run_id: str) -> dict[str, Any]:
        run = runs.resume(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        return run

    @router.delete("/runs/{run_id}", status_code=204)
    def delete_run(run_id: str) -> None:
        if not runs.delete(run_id):
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")

    @router.get("/runs/{run_id}/report")
    def run_report(run_id: str) -> dict[str, Any]:
        report_id = reports.by_run(run_id)
        if report_id is None:
            raise HTTPException(status_code=404, detail="E_REPORT_NOT_FOUND")
        return {"run_id": run_id, "report_id": report_id}

    @router.get("/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        payload = reports.get(report_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="E_REPORT_NOT_FOUND")
        return payload

    @router.get("/papers/{paper_id}")
    def get_paper(paper_id: str) -> dict[str, Any]:
        paper = runs.paper(paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="E_PAPER_NOT_FOUND")
        return paper

    @router.get("/topics/{topic_id}/conversations")
    def list_conversations(topic_id: str) -> list[dict[str, Any]]:
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id,created_at FROM chat_sessions WHERE topic_id=? ORDER BY created_at DESC",
                (topic_id,),
            ).fetchall()
            payload = []
            for row in rows:
                messages = conn.execute(
                    "SELECT role,content,created_at FROM chat_messages WHERE session_id=?"
                    " ORDER BY created_at",
                    (row["id"],),
                ).fetchall()
                first_user = next((m for m in messages if m["role"] == "user"), None)
                payload.append(
                    {
                        "id": row["id"],
                        "topic_id": topic_id,
                        "title": (first_user["content"][:44] if first_user else "New conversation"),
                        "created_at": row["created_at"],
                        "updated_at": messages[-1]["created_at"] if messages else row["created_at"],
                        "message_count": len(messages),
                    }
                )
        return payload

    @router.post("/topics/{topic_id}/conversations", status_code=201)
    def create_conversation(topic_id: str) -> dict[str, Any]:
        session_id = chat_store.create(topic_id)
        now = _now()
        return {
            "id": session_id,
            "topic_id": topic_id,
            "title": "New conversation",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

    @router.get("/conversations/{conversation_id}")
    def get_messages(conversation_id: str) -> list[dict[str, Any]]:
        history = chat_store.history(conversation_id)
        return [
            {
                "id": f"{conversation_id}:{index}",
                "conversation_id": conversation_id,
                "role": message["role"],
                "content": message["content"],
                "created_at": message["created_at"],
                "state": "done",
            }
            for index, message in enumerate(history)
        ]

    @router.post("/conversations/{conversation_id}/messages")
    def send_message(conversation_id: str, body: MessageBody) -> dict[str, Any]:
        content = body.content.strip()
        if not content:
            raise HTTPException(status_code=422, detail="E_INVALID_REQUEST")
        with db.connect() as conn:
            row = conn.execute(
                "SELECT topic_id FROM chat_sessions WHERE id=?", (conversation_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="E_CONVERSATION_NOT_FOUND")
        chat_store.append(conversation_id, "user", content)
        reply = build_chat_service(corpus_root).answer(
            topic_id=str(row["topic_id"]), message=content
        )
        chat_store.append(conversation_id, "assistant", reply.text, reply.citations)
        return {
            "id": f"{conversation_id}:{uuid.uuid4().hex[:8]}",
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": reply.text,
            "citations": reply.citations,
            "answered": reply.answered,
            "created_at": _now(),
            "state": "done",
        }

    @router.delete("/conversations/{conversation_id}", status_code=204)
    def delete_conversation(conversation_id: str) -> None:
        with db.connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id=?", (conversation_id,))
            conn.execute("DELETE FROM chat_sessions WHERE id=?", (conversation_id,))

    return router
