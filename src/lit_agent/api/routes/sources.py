"""源状态：`sync_state` 的游标与最近成功时间。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine
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
