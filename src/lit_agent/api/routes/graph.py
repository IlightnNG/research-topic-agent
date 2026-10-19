"""图查询路由：作者动向 / topic 网络图在 Phase 1 **显式未启用**（501）。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from lit_agent.errors import E_FEATURE_DISABLED

router = APIRouter()


def _not_enabled(feature: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "code": E_FEATURE_DISABLED,
            "message": f"{feature} 在 Phase 4 实现（P4）",
            "context": {"feature": feature},
        },
    )


@router.get("/authors/{author_id}")
def author_activity(author_id: str) -> JSONResponse:
    return _not_enabled(f"graph.authors({author_id})")


@router.get("/topics/{topic_id}/network")
def topic_network(topic_id: str) -> JSONResponse:
    return _not_enabled(f"graph.network({topic_id})")
