"""Direct Workflow report endpoint (Phase 3.5 / S1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.config import Settings
from lit_agent.db.session import connect
from lit_agent.errors import E_NOT_FOUND, LitError
from lit_agent.runtime.report_shell import run_direct_report

router = APIRouter(prefix="/api/topics", tags=["workflow"])


class DirectReportBody(BaseModel):
    limit: int = Field(default=100, ge=1, le=100)
    focus_hint: str | None = None
    run_id: str | None = None


@router.post("/{topic_id}/report-workflow")
def report_workflow(
    topic_id: str,
    body: DirectReportBody,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine) as conn:
        exists = conn.exec_driver_sql(
            "SELECT 1 FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
    if exists is None:
        raise LitError(E_NOT_FOUND, f"topic 不存在：{topic_id}")
    return run_direct_report(
        settings,
        topic_id,
        run_id=body.run_id,
        limit=body.limit,
        focus_hint=body.focus_hint,
    )
