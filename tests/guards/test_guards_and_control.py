"""S8/S9 验收：15 类守卫（触发/不触发/阶梯）与熔断、暂停、注入。"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.gateway.breaker import CircuitBreaker
from lit_agent.graph import guards as guards_mod
from lit_agent.graph.guards import GuardRail, RepeatToolGuard, guard_rail
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.models.verdict import GuardAction, GuardSeverity, Verdict
from lit_agent.runtime import control
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.graph_runner import run_graph


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
            paper_repo.upsert_many(
                conn,
                [Paper(paper_id="P1", title="Tool use", abstract="agents use tools", source="arxiv")],
            )
    finally:
        engine.dispose()
    return settings


# --------------------------------------------------------------------------- #
# S8：15 类守卫
# --------------------------------------------------------------------------- #
def _guard_classes() -> list[type]:
    return [
        obj
        for name, obj in vars(guards_mod).items()
        if inspect.isclass(obj) and name.endswith("Guard") and obj.__module__ == guards_mod.__name__
    ]


def test_fifteen_guards_registered() -> None:
    classes = _guard_classes()
    assert len(classes) >= 15, [cls.__name__ for cls in classes]
    rail = guard_rail(RunBudget())
    assert len(rail.guards) == 15
    assert len(set(rail.names)) == 15


#: 每条守卫：触发用 observation、默认不触发
TRIGGERS = {
    "ScopeDriftGuard": {"counters": {"drift_warn": 1}},
    "RetrievalFailureGuard": {"counters": {"retrieval_errors": 1}},
    "ZeroNewPapersGuard": {"counters": {"new_papers": 0}},
    "ParseFailureGuard": {"counters": {"parse_failed": 1}},
    "SchemaOutputGuard": {"counters": {"schema_errors": 1}},
    "EvidenceSufficiencyGuard": {"counters": {"cards": 0}},
    "CitationIntegrityGuard": {"counters": {"unresolved_citations": 1}},
    "GroundingRatioGuard": {"grounding_rate": 0.2},
    "LoopGuard": {"counters": {"loop": 1}},
    "TimeoutGuard": {"idle_seconds": 3600},
    "EvalQualityGuard": {"counters": {"eval_below": 1}},
}
SEQUENCE_TRIGGERS = {
    "NoProgressGuard": [{"produced": 1}, {"produced": 1}, {"produced": 1}],
    "StagnationGuard": [{"artifacts": 2}, {"artifacts": 2}, {"artifacts": 2}, {"artifacts": 2}],
}
CLASS_BY_NAME = {cls.__name__: cls for cls in _guard_classes()}


def _make(cls: type):
    if cls.__name__ == "BudgetGuardAdapter":
        budget = RunBudget(limit_usd=0.01)
        budget.add(cost_usd=0.05)
        return cls(budget=budget)
    return cls()


@pytest.mark.parametrize("name", list(TRIGGERS) + list(SEQUENCE_TRIGGERS))
def test_guard_fires(name: str) -> None:
    cls = CLASS_BY_NAME[name]
    guard = _make(cls)
    if name in TRIGGERS:
        verdict = guard.check(TRIGGERS[name])
    else:
        verdict = None
        for observation in SEQUENCE_TRIGGERS[name]:
            verdict = guard.check(observation)
    assert verdict is not None, f"{name} 未触发"
    assert isinstance(verdict, Verdict)


@pytest.mark.parametrize("name", list(TRIGGERS))
def test_guard_does_not_fire_on_empty(name: str) -> None:
    cls = CLASS_BY_NAME[name]
    guard = _make(cls)
    assert guard.check({"counters": {}}) is None, f"{name} 不应在空状态触发"


def test_budget_guard_is_part_of_rail() -> None:
    budget = RunBudget(limit_usd=0.01)
    budget.add(cost_usd=0.02)
    verdict = guard_rail(budget).run({"counters": {}})
    assert verdict is not None
    assert verdict.action is GuardAction.ABORT


def test_repeat_tool_reminds_then_escalates() -> None:
    guard = RepeatToolGuard(remind_after=1, escalate_after=3)
    assert guard.check({"tool": "openalex_search"}) is None
    remind = guard.check({"tool": "openalex_search"})
    assert remind is not None and remind.action is GuardAction.RETRY
    assert "提醒" in remind.reasons[0]
    guard.check({"tool": "openalex_search"})
    escalate = guard.check({"tool": "openalex_search"})
    assert escalate is not None and escalate.action is GuardAction.REPLAN


def test_rail_takes_heaviest_action() -> None:
    soft = Verdict(ok=True, severity=GuardSeverity.WARN, action=GuardAction.DEGRADE, code="E_X")
    hard = Verdict(
        ok=False,
        severity=GuardSeverity.BLOCK,
        action=GuardAction.ABORT,
        code="E_Y",
        reasons=["blocked"],
    )

    class Soft:
        name = "soft"

        def check(self, observation):
            return soft

    class Hard:
        name = "hard"

        def check(self, observation):
            return hard

    assert GuardRail(guards=[Soft(), Hard()]).run({}) is hard


# --------------------------------------------------------------------------- #
# S9：熔断器
# --------------------------------------------------------------------------- #
def test_breaker_opens_after_threshold_and_recovers() -> None:
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=2, cooldown_s=10.0, clock=lambda: now["t"])

    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow() is False, "打开后必须拒绝"

    now["t"] = 11.0
    assert breaker.allow() is True, "冷却后进入 half_open 并放行一次"
    assert breaker.allow() is False, "half_open 只放行一次试探"
    breaker.record_success()
    assert breaker.state == "closed"
    assert breaker.snapshot()["failures"] == 0


def test_breaker_half_open_failure_reopens() -> None:
    now = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, cooldown_s=5.0, clock=lambda: now["t"])
    breaker.record_failure()
    now["t"] = 6.0
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow() is False


# --------------------------------------------------------------------------- #
# S9：暂停 / 续跑 / 注入
# --------------------------------------------------------------------------- #
def test_pause_at_boundary_then_resume(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    control.request_pause("p9-run")

    paused = run_graph(settings, "ai-agents", run_id="p9-run")
    assert paused["state"] == "paused"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            state = conn.execute(text("SELECT state FROM runs WHERE id='p9-run'")).scalar_one()
    finally:
        engine.dispose()
    assert state == "paused"

    resumed = run_graph(settings, "ai-agents", run_id="p9-run", resume=True)
    assert resumed["state"] == "succeeded", resumed


def test_inject_prompt_is_recorded_and_merged(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    control.inject_prompt("i9-run", "focus on tool use")
    result = run_graph(settings, "ai-agents", run_id="i9-run")
    assert result["state"] == "succeeded"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            payloads = [
                row[0]
                for row in conn.execute(
                    text("SELECT payload_json FROM run_events WHERE run_id='i9-run'")
                ).all()
            ]
            focus = conn.execute(
                text("SELECT focus_hint FROM runs WHERE id='i9-run'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert focus and "tool use" in str(focus), "注入内容必须进入 run 的 focus_hint"
    assert any("focus on tool use" in (payload or "") for payload in payloads), "必须留下 inject 事件"
