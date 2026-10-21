"""十节点图的执行器（S2/S3/S4）：事件包装 + 条件边解释 + 续跑。

职责边界
- **节点**（`graph/nodes.py`）只做数据工作，不写事件；
- **本模块**负责：拿锁建 run、每阶段前后发 `phase_change`（带 `dedupe_key` 保证幂等）、
  解释 `state.edge`（abort/replan/...）、写阶段状态、收尾、失败报告。
- 续跑：`resume=True` 时调用 `graph.invoke(None)`，已完成的节点不会重跑（checkpoint 语义），
  因此**不会重复发 `phase_change start`**。
"""

from __future__ import annotations

from typing import Any

from lit_agent.config import Settings
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_LOCK_HELD, E_UNEXPECTED, LitError
from lit_agent.graph.checkpoint import open_checkpointer, thread_config
from lit_agent.graph.pipeline import build_phase2_graph
from lit_agent.graph.state import new_state
from lit_agent.models._base import Severity
from lit_agent.models.event import EventType
from lit_agent.models.run import RunState
from lit_agent.runtime import control, jobs
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.events import SqliteEventLog
from lit_agent.runtime.runner import new_run_id, prepare_run

__all__ = ["run_graph"]


class SimulatedCrash(RuntimeError):
    """测试用：模拟进程中断（run 保持 running，便于验证续跑）。"""


def _set_stage(settings: Settings, run_id: str, stage: str, *, completed: bool) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            run_repo.set_stage(conn, run_id, stage, completed=completed)
    finally:
        engine.dispose()


def run_graph(
    settings: Settings,
    topic_id: str,
    *,
    run_id: str | None = None,
    checkpoint_path: str | None = None,
    focus_hint: str | None = None,
    resume: bool = False,
    crash_after_stage: str | None = None,
    budget: RunBudget | None = None,
) -> dict[str, Any]:
    """执行十节点图。`resume=True` 时从 checkpoint 续跑（同一 run_id）。"""
    rid = run_id or new_run_id()
    if resume and run_id is None:
        raise LitError(E_UNEXPECTED, "续跑必须显式提供 run_id")

    engine = make_engine(settings)
    log = SqliteEventLog(engine, rid)
    run_budget = budget or RunBudget(limit_usd=settings.routing.run_cost_budget_usd)
    ckpt_path = checkpoint_path or f"{settings.storage.data_root}/checkpoints/{rid}.sqlite"
    saver, connection = open_checkpointer(ckpt_path)

    def stage_node(name: str) -> Any:
        from lit_agent.graph.nodes import Phase2Nodes

        impl = Phase2Nodes(settings)

        def node(state: dict[str, Any]) -> dict[str, Any]:
            if control.is_aborted(rid):
                raise LitError("E_RUN_ABORTED", "运行被人工中止", context={"run_id": rid, "stage": name})
            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                payload={"phase": "start"},
                dedupe_key=f"{name}:start",
            )
            _set_stage(settings, rid, name, completed=False)
            patch = getattr(impl, name)(state)  # 节点只做数据工作
            _set_stage(settings, rid, name, completed=True)
            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                payload={"phase": "end", "artifacts": len(patch.get("artifacts") or {})},
                dedupe_key=f"{name}:end",
            )
            if crash_after_stage == name:
                # 模拟进程中断：不 finish，checkpoint 已由 LangGraph 写盘
                raise SimulatedCrash(f"simulated crash after {name}")
            return patch

        return node

    from lit_agent.graph.nodes import PHASE2_STAGES

    graph = build_phase2_graph(
        settings,
        nodes={name: stage_node(name) for name in PHASE2_STAGES},
        checkpointer=saver,
    )
    config = thread_config(rid)

    try:
        if not resume:
            prepare_run(settings, topic_id, rid, focus_hint, engine=engine)
        state = new_state(run_id=rid, topic_id=topic_id)
        state["budget"] = run_budget.snapshot()
        state["edge"] = None
        state["focus_hint"] = focus_hint

        payload = None if resume else state
        log.emit(
            EventType.PHASE_CHANGE,
            stage="run",
            payload={"phase": "start", "topic_id": topic_id, "resume": resume},
            dedupe_key=f"run:start:{'resume' if resume else 'fresh'}",
        )

        final = graph.invoke(payload, config)

        # 条件边：abort 直接终止；其余动作以 annotate 事件记录（由后续步骤解释）
        edge = final.get("edge")
        if edge == "abort":
            log.emit(
                EventType.GUARD_TRIGGER,
                stage=final.get("stage") or "run",
                agent="graph",
                severity=Severity.ERROR,
                payload={"edge": "abort", "reason": "conditional edge requested abort"},
            )
            jobs.finish(settings, rid, state=RunState.ABORTED, error_code="E_GUARD_LOOP", engine=engine)
            return {"run_id": rid, "state": "aborted", "stage": final.get("stage")}
        if edge:
            log.emit(
                EventType.GUARD_TRIGGER,
                stage=final.get("stage") or "run",
                agent="graph",
                severity=Severity.WARNING,
                payload={"edge": edge},
                dedupe_key=f"edge:{final.get('stage')}:{edge}",
            )

        jobs.finish(settings, rid, state=RunState.SUCCEEDED, engine=engine)
        return {
            "run_id": rid,
            "state": "succeeded",
            "stage": final.get("stage"),
            "stages": final.get("artifacts"),
            "counters": final.get("counters"),
            "events": log.count(),
            "budget": run_budget.snapshot(),
        }
    except SimulatedCrash:
        # 刻意不 finish：run 保持 running，用于验证"续跑不重复"
        raise
    except LitError as exc:
        if exc.code == E_LOCK_HELD:
            raise
        report = jobs.failure_report(settings, rid, exc)
        log.emit(
            EventType.ERROR,
            stage="run",
            severity=Severity.ERROR,
            payload={**exc.to_event_payload(), "failure_report": report},
        )
        jobs.finish(settings, rid, state=RunState.FAILED, error_code=exc.code, engine=engine)
        return {"run_id": rid, "state": "failed", "error_code": exc.code, "failure_report": report}
    finally:
        control.clear(rid)
        connection.close()
        engine.dispose()
