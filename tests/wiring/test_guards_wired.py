"""S1 接线测试①：15 类守卫必须真的在生产链路里执行（S3 修复）。

判据：预算已超限 → run 必须 aborted，且事件里出现 guard_trigger。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from lit_agent.db.session import connect, make_engine
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import fetch_events, prepare


def test_budget_guard_aborts_production_run(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    budget = RunBudget(limit_usd=0.001)
    budget.add(cost_usd=0.01)  # 已超限

    result = run_graph(settings, "ai-agents", run_id="w-guard", budget=budget)

    assert result["state"] == "aborted", result
    assert result["error_code"] == "E_BUDGET_EXCEEDED"

    events = fetch_events(settings, "w-guard")
    triggers = [event for event in events if event["type"] == "guard_trigger"]
    assert triggers, "预算超限必须留下 guard_trigger（守卫/门禁未接线）"
    assert any(event["payload"].get("code") == "E_BUDGET_EXCEEDED" for event in triggers)

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            reports = conn.execute(
                text("SELECT COUNT(*) FROM reports WHERE run_id='w-guard'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert int(reports) == 0, "中止的 run 不得写报告"
