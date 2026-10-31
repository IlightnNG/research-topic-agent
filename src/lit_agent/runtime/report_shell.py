"""Direct Report run shell (Phase 3.5 / S1-S2).

This is the new API/CLI seam: it does not execute the legacy ten-node graph.
"""

from __future__ import annotations

import uuid
from typing import Any

from lit_agent.config import Settings
from lit_agent.db.session import make_engine
from lit_agent.models.event import EventType
from lit_agent.models.run import RunState
from lit_agent.runtime import jobs
from lit_agent.runtime.events import SqliteEventLog
from lit_agent.runtime.runner import persist_report_draft, prepare_run
from lit_agent.workflow.report import ReportWorkflow

__all__ = ["run_direct_report"]


def run_direct_report(
    settings: Settings,
    topic_id: str,
    *,
    run_id: str | None = None,
    limit: int = 100,
    focus_hint: str | None = None,
    gateway: Any | None = None,
) -> dict[str, Any]:
    rid = run_id or f"run-{uuid.uuid4().hex[:10]}"
    prepare_run(settings, topic_id, rid, focus_hint)
    event_engine = make_engine(settings)
    log = SqliteEventLog(event_engine, rid)

    def event_sink(event: dict[str, Any]) -> None:
        if event.get("event") in {"node.started", "node.finished", "node.failed"}:
            log.emit(
                EventType.PHASE_CHANGE,
                stage="report",
                payload={
                    "phase": "step",
                    "step": str(event.get("node_id") or ""),
                    "status": str(event.get("event") or ""),
                    "error": str(event.get("error") or ""),
                },
            )

    try:
        log.emit(EventType.PHASE_CHANGE, stage="run", payload={"phase": "start", "run_id": rid})
        report, context = ReportWorkflow(
            settings, gateway=gateway, event_sink=event_sink
        ).run(
            run_id=rid,
            topic_id=topic_id,
            limit=limit,
            focus_hint=focus_hint,
            title=f"Weekly report: {topic_id}",
        )
        persist_report_draft(settings, rid, report)
        from lit_agent.eval.metric_store import collect_report_points

        collect_report_points(settings, rid)
        jobs.finish(settings, rid, state=RunState.SUCCEEDED)
        log.emit(
            EventType.PHASE_CHANGE,
            stage="run",
            payload={"phase": "end", "run_id": rid, "state": "succeeded"},
        )
        return {
            "run_id": rid,
            "report_id": report.report_id,
            "claims": report.n_claims,
            "sections": len(report.sections),
            "papers": len(context.cards),
            "state": "succeeded",
        }
    except Exception as exc:  # noqa: BLE001 - run must settle as failed
        jobs.finish(settings, rid, state=RunState.FAILED, error_code="E_UNEXPECTED")
        log.emit(
            EventType.PHASE_CHANGE,
            stage="run",
            payload={"phase": "end", "run_id": rid, "state": "failed"},
        )
        raise RuntimeError(f"direct report failed: {exc}") from exc
    finally:
        event_engine.dispose()
