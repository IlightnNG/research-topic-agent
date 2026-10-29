"""源状态：`sync_state` 的游标与最近成功时间。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.api.schemas import SourcePreviewRequest, SourceSuggestRequest
from lit_agent.config import Settings
from lit_agent.db.session import connect

router = APIRouter()


@router.get("")
def list_sources(engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = conn.execute(
            text(
                "SELECT source, selector, last_cursor, last_since, last_success_at, status, error_code"
                " FROM sync_state ORDER BY source, selector"
            )
        ).all()
    items = [
        {
            "source": row[0],
            "selector": row[1],
            "last_cursor": row[2],
            "last_since": row[3],
            "last_success_at": row[4],
            "status": row[5],
            "error_code": row[6],
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


@router.post("/preview")
def preview_sources(
    body: SourcePreviewRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from lit_agent.sources.preview import preview_selector

    return preview_selector(settings, body.selector, limit=body.limit)


@router.post("/suggest")
def suggest_sources(
    body: SourceSuggestRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from lit_agent.sources.suggest import suggest_sources as suggest

    gateway = None
    if settings.pipeline.llm != "off" and (
        settings.providers.cloud.api_key is not None
        or settings.providers.cloud.api_key_env
    ):
        from lit_agent.gateway.llm import LLMGateway

        gateway = LLMGateway(settings)
    try:
        return suggest(settings, body.scope_statement, gateway=gateway)
    finally:
        if gateway is not None:
            gateway.close()
