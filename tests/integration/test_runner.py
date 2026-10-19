"""Step 1.11 运行器/守卫/锁/看门狗（离线：注入阶段函数）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.repo import locks as lock_repo
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import E_LOCK_HELD, E_SRC_TIMEOUT, LitError
from lit_agent.models.results import RunContext, StageResult
from lit_agent.models.run import RunState
from lit_agent.models.topic import Topic
from lit_agent.runtime import jobs
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.runner import default_stages, run_topic
from lit_agent.runtime.watchdog import scan


def prepare(tmp_path: Path) -> Settings:
    from lit_agent.db.repo import topics as topic_repo

    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="llm agents"))
    finally:
        engine.dispose()
    return settings


def events(settings: Settings, run_id: str) -> list[dict]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT type, stage, payload_json FROM run_events WHERE run_id=:r ORDER BY seq"
                ),
                {"r": run_id},
            ).all()
    finally:
        engine.dispose()
    return [{"type": row[0], "stage": row[1], "payload": row[2]} for row in rows]


def run_state(settings: Settings, run_id: str) -> dict:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return dict(run_repo.get(conn, run_id)._mapping)
    finally:
        engine.dispose()


def test_run_succeeds_and_releases_lock(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="run-ok")

    assert result["state"] == "succeeded"
    assert result["events"] >= 5
    assert set(result["stages"]) == {"intake", "ingest", "curate", "report"}
    assert run_state(settings, "run-ok")["state"] == RunState.SUCCEEDED.value

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            assert lock_repo.get(conn, "ai-agents") is None, "run 结束必须释放锁"
    finally:
        engine.dispose()
    assert any(event["type"] == "report_written" for event in events(settings, "run-ok"))


def test_second_run_on_same_topic_is_blocked(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    jobs.start(settings, "ai-agents", run_id="run-held")
    with pytest.raises(LitError) as excinfo:
        run_topic(settings, "ai-agents", run_id="run-blocked")
    assert excinfo.value.code == E_LOCK_HELD
    jobs.finish(settings, "run-held", state=RunState.ABORTED)


def test_failure_writes_four_part_report_and_error_event(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    def boom(_ctx: RunContext) -> StageResult:
        raise LitError(E_SRC_TIMEOUT, "source timed out")

    result = run_topic(settings, "ai-agents", run_id="run-fail", stages={"retrieve": boom})

    assert result["state"] == "failed"
    assert result["error_code"] == E_SRC_TIMEOUT
    report = result["failure_report"]
    assert {"run_id", "error_code", "last_ok_stage", "produced_events", "suggestion"} <= set(report)
    assert run_state(settings, "run-fail")["error_code"] == E_SRC_TIMEOUT
    errors = [event for event in events(settings, "run-fail") if event["type"] == "error"]
    assert errors and "failure_report" in errors[-1]["payload"]


def test_budget_guard_aborts_run(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    budget = RunBudget(limit_usd=0.01)
    budget.add(cost_usd=0.05)

    result = run_topic(settings, "ai-agents", run_id="run-budget", budget=budget)

    assert result["state"] == "failed"
    assert result["error_code"] == "E_BUDGET_EXCEEDED"
    assert any(event["type"] == "guard_trigger" for event in events(settings, "run-budget"))


def test_no_progress_guard_emits_warning(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    def flat(_ctx: RunContext) -> StageResult:
        return StageResult(stage="flat", artifacts={})

    stages = {f"flat{index}": flat for index in range(4)}
    result = run_topic(
        settings, "ai-agents", run_id="run-stall", stages=stages, no_progress_steps=2
    )

    assert result["state"] == "succeeded"  # 停滞只降级告警，不终止
    guard_events = [
        event for event in events(settings, "run-stall") if event["type"] == "guard_trigger"
    ]
    assert guard_events, "连续无进展必须发出 guard_trigger"


def test_watchdog_detects_stale_run(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="run-wd")

    report = scan(settings, "run-wd", stale_seconds=0)
    assert report["stale"] is True
    assert any(event["type"] == "guard_trigger" for event in events(settings, "run-wd"))


def test_cleanup_orphans_marks_running_without_lock(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    jobs.start(settings, "ai-agents", run_id="run-orphan")
    # 模拟进程崩溃：锁没了，但 run 仍是 running
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            lock_repo.release(conn, "ai-agents")
    finally:
        engine.dispose()

    result = jobs.cleanup_orphans(settings)
    assert "run-orphan" in result["aborted_runs"]
    assert run_state(settings, "run-orphan")["state"] == RunState.ABORTED.value


def test_default_stages_are_callable() -> None:
    stages = default_stages()
    assert list(stages) == ["intake", "retrieve", "report"]
    for name, fn in stages.items():
        result = fn(RunContext(run_id="r", topic_id="t", stage=name))
        assert result.stage == name
