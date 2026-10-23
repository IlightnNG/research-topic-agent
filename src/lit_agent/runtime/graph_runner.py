"""十节点图的执行器（S2/S3：门禁 + 监督者 + 两阶段提交）。

职责边界
- **节点**只做数据工作，返回 `pending_writes`，不写库；
- **本模块**负责：拿锁建 run、每阶段事件（带 attempt）、跑门禁与守卫、
  执行 `Decision`（S3：abort/degrade）、门禁通过后提交写入、收尾、续跑。
"""

from __future__ import annotations

from typing import Any

from lit_agent.config import Settings
from lit_agent.contracts.nodeio import Decision, GateResult
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_LOCK_HELD, E_UNEXPECTED, LitError
from lit_agent.graph.checkpoint import open_checkpointer, thread_config
from lit_agent.graph.gates import run_gates
from lit_agent.graph.guards import guard_rail
from lit_agent.graph.pipeline import build_phase2_graph
from lit_agent.graph.state import new_state
from lit_agent.graph.supervisor import decide
from lit_agent.models._base import Severity
from lit_agent.models.event import EventType
from lit_agent.models.run import RunState
from lit_agent.runtime import control, jobs
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.commit import commit_pending
from lit_agent.runtime.context import RunContext
from lit_agent.runtime.events import SqliteEventLog
from lit_agent.runtime.runner import new_run_id, prepare_run

__all__ = ["run_graph"]


class SimulatedCrash(RuntimeError):
    """测试用：模拟进程中断（run 保持 running，便于验证续跑）。"""


class PauseRequested(RuntimeError):
    """人工暂停：在阶段边界退出，run 置为 paused，checkpoint 保留。"""


class RunAborted(RuntimeError):
    """门禁/守卫要求终止。"""

    def __init__(self, decision: Decision) -> None:
        super().__init__(decision.code)
        self.decision = decision


def _persist_focus_hint(settings: Settings, run_id: str, focus_hint: str | None) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            run_repo.update_ui_fields(conn, run_id, focus_hint=focus_hint)
    finally:
        engine.dispose()


def _set_stage(settings: Settings, run_id: str, stage: str, *, completed: bool) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            run_repo.set_stage(conn, run_id, stage, completed=completed)
    finally:
        engine.dispose()


def _gate_payload(gates: list[GateResult]) -> list[dict[str, Any]]:
    return [
        {
            "name": gate.name,
            "code": gate.code,
            "action": gate.action,
            "reasons": gate.reasons,
            "details": gate.details,
        }
        for gate in gates
    ]


def run_graph(
    settings: Settings,
    topic_id: str,
    *,
    run_id: str | None = None,
    checkpoint_path: str | None = None,
    focus_hint: str | None = None,
    resume: bool = False,
    prestarted: bool = False,
    crash_after_stage: str | None = None,
    budget: RunBudget | None = None,
    gateway: Any | None = None,
    tools: Any | None = None,
    pdf_enabled: bool | None = None,
) -> dict[str, Any]:
    """执行十节点图。`resume=True` 时从 checkpoint 续跑（同一 run_id）。"""
    rid = run_id or new_run_id()
    if resume and run_id is None:
        raise LitError(E_UNEXPECTED, "续跑必须显式提供 run_id")

    engine = make_engine(settings)
    log = SqliteEventLog(engine, rid)
    run_budget = budget or RunBudget.from_db(
        settings, rid, limit_usd=settings.pipeline.limits.max_run_usd
    )
    ckpt_path = checkpoint_path or f"{settings.storage.data_root}/checkpoints/{rid}.sqlite"
    saver, connection = open_checkpointer(ckpt_path)

    pdf_on = settings.pipeline.pdf_enabled if pdf_enabled is None else pdf_enabled
    if pdf_on and tools is None:
        from lit_agent.tools.registry import default_registry

        tools = default_registry()

    llm_mode = settings.pipeline.llm
    if gateway is None and llm_mode != "off":
        has_key = settings.providers.cloud.api_key is not None
        if llm_mode == "on" or (llm_mode == "auto" and has_key):
            from lit_agent.gateway.llm import LLMGateway

            gateway = LLMGateway(settings, budget=run_budget)

    ctx = RunContext(
        settings=settings,
        run_id=rid,
        topic_id=topic_id,
        budget=run_budget,
        gateway=gateway,
        tools=tools,
        pdf_enabled=pdf_on,
        log=log,
        transitions_enabled=True,  # S4：有界回边已启用
        gates_enabled=settings.pipeline.gates.enabled,
    )
    rail = guard_rail(run_budget)

    def stage_node(name: str) -> Any:
        from lit_agent.graph.nodes import Phase2Nodes

        impl = Phase2Nodes(settings, ctx=ctx)

        def node(state: dict[str, Any]) -> dict[str, Any]:
            if control.is_aborted(rid):
                raise LitError(
                    "E_RUN_ABORTED", "运行被人工中止", context={"run_id": rid, "stage": name}
                )
            if control.is_paused(rid):
                raise PauseRequested(f"paused before {name}")

            attempts = dict(state.get("attempts") or {})
            attempt = int(attempts.get(name, 0)) + 1
            attempts[name] = attempt

            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                payload={"phase": "start", "attempt": attempt},
                dedupe_key=f"{name}:start:{attempt}",
            )
            _set_stage(settings, rid, name, completed=False)

            patch = getattr(impl, name)(state)  # 只计算，不写库
            gates = run_gates(name, patch, state, ctx) if ctx.gates_enabled else []
            guard_verdict = rail.run(ctx.observation({**state, **patch}, name))
            decision = decide(
                stage=name, gates=gates, guard=guard_verdict, ctx=ctx, attempt=attempt
            )

            if decision.action == "abort":
                log.emit(
                    EventType.PHASE_CHANGE,
                    stage=name,
                    payload={"phase": "end", "attempt": attempt, "ok": False, "gates": _gate_payload(gates)},
                    dedupe_key=f"{name}:end:{attempt}",
                )
                log.emit(
                    EventType.GUARD_TRIGGER,
                    stage=name,
                    agent="supervisor",
                    severity=Severity.ERROR,
                    payload={
                        "gate": gates[0].name if gates else "guard",
                        "code": decision.code,
                        "action": decision.action,
                        "reasons": decision.reasons,
                        "attempt": attempt,
                        "source": decision.source,
                    },
                    dedupe_key=f"guard:{name}:{attempt}:abort",
                )
                raise RunAborted(decision)

            executed = decision
            if decision.action in {"retry", "repair", "replan"}:
                target = decision.target or name
                done = int(attempts.get(target, 0))
                limit = int(getattr(ctx.limits_cfg, "max_attempts", {}).get(target, 1))
                if not ctx.transitions_enabled or done >= limit:
                    reason = (
                        "回边未启用"
                        if not ctx.transitions_enabled
                        else f"尝试次数用尽（{done}/{limit}），降级继续"
                    )
                    log.emit(
                        EventType.GUARD_TRIGGER,
                        stage=name,
                        agent="supervisor",
                        severity=Severity.WARNING,
                        payload={
                            "gate": gates[0].name if gates else "guard",
                            "code": decision.code,
                            "action": decision.action,
                            "target": target,
                            "reasons": [*decision.reasons, reason],
                            "attempt": attempt,
                            "source": decision.source,
                            "codes": sorted({decision.code, *(gate.code for gate in gates)}),
                            "exhausted": ctx.transitions_enabled,
                        },
                        dedupe_key=f"guard:{name}:{attempt}:exhausted",
                    )
                    executed = decision.model_copy(
                        update={"action": "degrade", "reasons": [*decision.reasons, reason]}
                    )
                else:
                    log.emit(
                        EventType.GUARD_TRIGGER,
                        stage=name,
                        agent="supervisor",
                        severity=Severity.WARNING,
                        payload={
                            "gate": gates[0].name if gates else "guard",
                            "code": decision.code,
                            "action": decision.action,
                            "target": target,
                            "reasons": decision.reasons,
                            "attempt": attempt,
                            "source": decision.source,
                            "codes": sorted({decision.code, *(gate.code for gate in gates)}),
                        },
                        dedupe_key=f"guard:{name}:{attempt}:{decision.action}",
                    )
                    log.emit(
                        EventType.RECOVERY,
                        stage=name,
                        payload={
                            "from_stage": name,
                            "to_stage": target,
                            "attempt": attempt,
                            "reason": decision.reasons[0] if decision.reasons else decision.code,
                        },
                        dedupe_key=f"recovery:{name}:{attempt}:{target}",
                    )
                    log.emit(
                        EventType.PHASE_CHANGE,
                        stage=name,
                        payload={
                            "phase": "end",
                            "attempt": attempt,
                            "ok": False,
                            "action": decision.action,
                            "gates": _gate_payload(gates),
                        },
                        dedupe_key=f"{name}:end:{attempt}",
                    )
                    patch["attempts"] = attempts
                    patch["decisions"] = [decision.model_dump(mode="json")]
                    return patch
            elif decision.action != "continue":
                log.emit(
                    EventType.GUARD_TRIGGER,
                    stage=name,
                    agent="supervisor",
                    severity=Severity.WARNING,
                    payload={
                        "gate": gates[0].name if gates else "guard",
                        "code": decision.code,
                        "action": decision.action,
                        "reasons": decision.reasons,
                        "attempt": attempt,
                        "source": decision.source,
                        "codes": sorted({decision.code, *(gate.code for gate in gates)}),
                    },
                    dedupe_key=f"guard:{name}:{attempt}:{decision.action}",
                )

            commit_summary = commit_pending(ctx, state, patch, executed)

            _set_stage(settings, rid, name, completed=True)
            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                payload={
                    "phase": "end",
                    "attempt": attempt,
                    "ok": executed.action in {"continue", "degrade"},
                    "action": executed.action,
                    "gates": _gate_payload(gates),
                    "artifacts": len(patch.get("artifacts") or {}),
                    **commit_summary,
                },
                dedupe_key=f"{name}:end:{attempt}",
            )
            if crash_after_stage == name:
                raise SimulatedCrash(f"simulated crash after {name}")

            patch["attempts"] = attempts
            patch["decisions"] = [executed.model_dump(mode="json")]
            return patch

        return node

    from lit_agent.graph.nodes import PHASE2_STAGES

    graph = build_phase2_graph(
        settings,
        nodes={name: stage_node(name) for name in PHASE2_STAGES},
        checkpointer=saver,
    )
    config = thread_config(rid)
    config["recursion_limit"] = settings.pipeline.limits.recursion_limit

    try:
        if not resume and not prestarted:
            prepare_run(settings, topic_id, rid, focus_hint, engine=engine)
        state = new_state(run_id=rid, topic_id=topic_id)
        state["budget"] = run_budget.snapshot()
        state["edge"] = None
        injected = control.consume_inject(rid)
        merged_hint = " ".join([part for part in [focus_hint, *injected] if part]) or None
        state["focus_hint"] = merged_hint
        if injected:
            _persist_focus_hint(settings, rid, merged_hint)
            log.emit(
                EventType.PHASE_CHANGE,
                stage="run",
                payload={"phase": "inject", "prompts": injected},
                dedupe_key=f"inject:{len(injected)}:{'|'.join(injected)[:80]}",
            )

        payload = None if resume else state
        log.emit(
            EventType.PHASE_CHANGE,
            stage="run",
            payload={"phase": "start", "topic_id": topic_id, "resume": resume},
            dedupe_key=f"run:start:{'resume' if resume else 'fresh'}",
        )

        final = graph.invoke(payload, config)

        # 兼容旧的条件边注解（S4 起由 decisions 驱动，这里只做审计）
        edges = list(final.get("edges") or [])
        for edge in edges:
            if edge == "abort":
                continue
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
    except RunAborted as aborted:
        log.emit(
            EventType.ERROR,
            stage="run",
            severity=Severity.ERROR,
            payload={
                "code": aborted.decision.code,
                "message": "; ".join(aborted.decision.reasons),
                "action": aborted.decision.action,
            },
        )
        jobs.finish(
            settings, rid, state=RunState.ABORTED, error_code=aborted.decision.code, engine=engine
        )
        return {
            "run_id": rid,
            "state": "aborted",
            "error_code": aborted.decision.code,
            "decision": aborted.decision.model_dump(mode="json"),
        }
    except PauseRequested:
        control.clear_pause(rid)
        jobs.finish(settings, rid, state=RunState.PAUSED, error_code=None, engine=engine)
        return {"run_id": rid, "state": "paused"}
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
        ctx.close()
        connection.close()
        engine.dispose()
