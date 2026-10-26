"""3.5 / S22：轨迹指标（步数、工具调用、修复率、升级率、停止原因）。

从 run_events 派生，不新增事件类型（ADR-0006）。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine
from lit_agent.graph.nodes import PHASE2_STAGES

__all__ = ["trajectory_metrics"]


def trajectory_metrics(settings: Settings, run_id: str) -> dict[str, Any]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT type, stage, payload_json FROM run_events"
                    " WHERE run_id = :rid ORDER BY seq"
                ),
                {"rid": run_id},
            ).all()
    finally:
        engine.dispose()

    steps = 0
    tool_calls = 0
    attempts: dict[str, int] = {}
    repairs = 0
    escalations = 0
    stop_reason = ""

    for event_type, stage, payload_json in rows:
        try:
            payload = json.loads(payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if event_type == "phase_change" and payload.get("phase") == "start":
            name = str(stage)
            if name in PHASE2_STAGES:
                steps += 1
                attempt = int(payload.get("attempt") or 1)
                attempts[name] = max(attempts.get(name, 0), attempt)
        elif event_type == "tool_call":
            tool_calls += 1
        elif event_type == "guard_trigger":
            action = str(payload.get("action") or "")
            if action in {"retry", "repair", "replan"}:
                repairs += 1
            if action in {"degrade", "abort"}:
                escalations += 1
        elif event_type == "recovery":
            escalations += 1

    if any(value > 1 for value in attempts.values()):
        stop_reason = "retried"
    elif escalations:
        stop_reason = "degraded"
    else:
        stop_reason = "clean"

    retries = sum(max(0, value - 1) for value in attempts.values())
    return {
        "steps_total": steps,
        "tool_calls": tool_calls,
        "retries_total": retries,
        "attempts_by_stage": attempts,
        "repair_rate": round(repairs / steps, 4) if steps else 0.0,
        "escalation_rate": round(escalations / steps, 4) if steps else 0.0,
        "stop_reason": stop_reason,
    }
