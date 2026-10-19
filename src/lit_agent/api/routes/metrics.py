"""只读指标汇总（P1 极简：计数 + 成本；完整指标在 1.18）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine
from lit_agent.db.session import connect

router = APIRouter()


@router.get("/summary")
def summary(engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM runs),"
                " (SELECT COUNT(*) FROM run_events),"
                " (SELECT COUNT(*) FROM reports),"
                " (SELECT COUNT(*) FROM papers),"
                " (SELECT COALESCE(SUM(cost), 0.0) FROM llm_calls)"
            )
        ).one()
    return {
        "runs": int(row[0]),
        "events": int(row[1]),
        "reports": int(row[2]),
        "papers": int(row[3]),
        "llm_cost_usd": round(float(row[4]), 6),
    }
