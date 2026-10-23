"""S2 验收：单 run LLM 调用数硬顶（DB 计数，不依赖内存）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from tests.wiring import fetch_events, prepare

from lit_agent.config import LimitSettings, PipelineSettings
from lit_agent.db.session import connect, make_engine
from lit_agent.runtime.graph_runner import run_graph

INSERT = text(
    "INSERT INTO llm_calls(ts, run_id, agent, provider, model, request_sha, cache_hit,"
    " req_tokens, resp_tokens, cost, cost_estimated, latency_ms, degraded, ok)"
    " VALUES (:ts, :rid, 'analyst', 'test', 'test', :sha, 0, 10, 5, 0.0, 0, 12, 0, 1)"
)


def _seed_calls(settings, run_id: str, count: int) -> None:
    from lit_agent.runtime import jobs

    engine = make_engine(settings)
    try:
        jobs.start(settings, "ai-agents", run_id=run_id, engine=engine)
        with connect(engine, immediate=True) as conn:
            for index in range(count):
                conn.execute(
                    INSERT,
                    {
                        "ts": f"2026-10-23T00:00:{index:02d}Z",
                        "rid": run_id,
                        "sha": f"sha-{index}",
                    },
                )
    finally:
        engine.dispose()


def _report_count(settings, run_id: str) -> int:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return int(
                conn.execute(
                    text("SELECT COUNT(*) FROM reports WHERE run_id = :rid"), {"rid": run_id}
                ).scalar_one()
            )
    finally:
        engine.dispose()


def test_aborts_when_call_budget_exhausted(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    _seed_calls(settings, "cap-12", 12)

    result = run_graph(settings, "ai-agents", run_id="cap-12", prestarted=True)

    assert result["state"] == "aborted", result
    assert result["error_code"] == "E_BUDGET_EXCEEDED"
    assert _report_count(settings, "cap-12") == 0

    events = fetch_events(settings, "cap-12")
    codes = {
        event["payload"].get("code")
        for event in events
        if event["type"] == "guard_trigger"
    }
    assert "E_BUDGET_EXCEEDED" in codes, codes
    aborts = [
        event["payload"]
        for event in events
        if event["type"] == "guard_trigger"
        and event["payload"].get("code") == "E_BUDGET_EXCEEDED"
    ]
    assert aborts, "应有一条预算中止事件"
    assert aborts[0].get("gate") == "llm_calls", aborts[0]


def test_allows_run_below_cap(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    _seed_calls(settings, "cap-11", 11)

    result = run_graph(settings, "ai-agents", run_id="cap-11", prestarted=True)
    assert result["state"] == "succeeded", result
    assert _report_count(settings, "cap-11") == 1


def test_cap_comes_from_config(tmp_path: Path) -> None:
    base = prepare(tmp_path)
    settings = base.model_copy(
        update={"pipeline": PipelineSettings(limits=LimitSettings(max_total_llm_calls=2))}
    )
    _seed_calls(settings, "cap-2", 2)

    result = run_graph(settings, "ai-agents", run_id="cap-2", prestarted=True)
    assert result["state"] == "aborted", result
