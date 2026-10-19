"""Chat 路由：Phase 1 **显式未启用**（501，不是 404）。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from lit_agent.errors import E_FEATURE_DISABLED

router = APIRouter()


@router.get("/{topic_id}/chat")
def chat_history(topic_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "code": E_FEATURE_DISABLED,
            "message": "Chat 在 Phase 3 实现（P3）",
            "context": {"feature": "agents.chat", "topic_id": topic_id},
        },
    )


@router.post("/{topic_id}/chat")
def chat_send(topic_id: str) -> JSONResponse:
    return chat_history(topic_id)
