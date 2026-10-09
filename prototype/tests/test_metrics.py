"""S7 指标聚合单测（纯函数，用合成事件回归口径）。

锁住的口径（`evaluation-plan.md` §5）：
- grounding 支持率 = supported / verifiable；
- 幻觉率 = (contradicted + unsupported + **被丢弃的不可回查 claim**) / verifiable（§5.5）；
- 漂移/循环 → 事件计数；检出率 → 按故障族判定（**timeout 族看 error 事件、不看 guard_trigger**）；
- 同一 run 多次尝试 → 取**最后一条**同类事件，避免把数字算大。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lit_agent_min.models import Event, EventType, Severity
from steps.s7_metrics import (
    aggregate_all,
    aggregate_run,
    select_campaign,
)

BASE = datetime(2026, 10, 9, 3, 0, 0, tzinfo=UTC)


def _event(run_id: str, seq: int, type_: str, payload: dict, stage: str = "s") -> Event:
    return Event(
        run_id=run_id,
        seq=seq,
        ts=BASE + timedelta(seconds=seq),
        type=EventType(type_),
        stage=stage,
        severity=Severity.INFO,
        payload=payload,
    )


def _report_run(run_id: str, *, supported: int, contradicted: int, dropped: int = 0) -> list[Event]:
    claims = supported + contradicted + dropped
    events = [
        _event(run_id, 1, "phase_change", {"phase": "start"}),
        _event(
            run_id,
            2,
            "metric",
            {
                "kind": "grounding",
                "topic": "T1",
                "claims": supported + contradicted,
                "verifiable_claims": claims,
                "claims_supported": supported,
                "claims_contradicted": contradicted,
                "claims_unsupported": 0,
                "claims_dropped_ungrounded": dropped,
                "distinct_cited_papers": 3,
                "ungrounded_citation_count": 0,
                "topicality_mean": 0.15,
                "report_chars": 900,
            },
            stage="5.6_report",
        ),
        _event(
            run_id,
            3,
            "metric",
            {
                "kind": "run_summary",
                "claims": supported + contradicted,
                "cost_usd": 0.01,
                "seconds": 60.0,
                "llm_calls": 4,
                "network_calls": 4,
                "cache_hits": 0,
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "report_chars": 900,
            },
            stage="5.7_events",
        ),
    ]
    return events


def _guard_run(
    run_id: str,
    *,
    scenario: str,
    code: str | None,
    action: str,
    recovered: bool,
    aborted: bool,
    timeout_error: bool = False,
) -> list[Event]:
    events = [_event(run_id, 1, "phase_change", {"phase": "start", "scenario": scenario})]
    seq = 2
    if code:
        events.append(
            _event(
                run_id,
                seq,
                "guard_trigger",
                {"code": code, "action": action, "severity": "warning"},
            )
        )
        seq += 1
    if timeout_error:
        events.append(
            _event(run_id, seq, "error", {"error_code": "E_PROVIDER_TIMEOUT", "injected": True})
        )
        seq += 1
    events.append(
        _event(
            run_id,
            seq,
            "metric",
            {"scenario": scenario, "recovered": recovered, "aborted": aborted},
        )
    )
    return events


# ---- 单 run ---- #
def test_grounding_and_hallucination_rates() -> None:
    row = aggregate_run("r1", _report_run("r1", supported=8, contradicted=1, dropped=1))
    assert row["verifiable_claims"] == 10
    assert row["grounding_support_rate"] == 0.8
    # §5.5：被丢弃的不可回查 claim 计入 unsupported，而不是从分母消失
    assert row["claims_unsupported"] == 1
    assert row["hallucination_rate"] == 0.2
    assert row["severe_hallucination_rate"] == 0.1


def test_last_metric_event_wins_for_repeated_attempts() -> None:
    """同一 run 多次尝试：取最后一条（否则重复尝试会把分子分母都算大）。"""
    events = _report_run("r1", supported=1, contradicted=0)
    events += [
        _event(
            "r1",
            10,
            "metric",
            {
                "kind": "grounding",
                "claims": 4,
                "verifiable_claims": 4,
                "claims_supported": 4,
                "claims_contradicted": 0,
                "claims_unsupported": 0,
                "claims_dropped_ungrounded": 0,
                "topicality_mean": 0.2,
                "report_chars": 1000,
            },
            stage="5.6_report",
        )
    ]
    row = aggregate_run("r1", events)
    assert row["verifiable_claims"] == 4
    assert row["grounding_support_rate"] == 1.0
    assert row["metric_events"] == 3


def test_guard_event_counting_and_actions() -> None:
    events = _guard_run(
        "g1", scenario="drift", code="E_GUARD_DRIFT", action="replan", recovered=True, aborted=False
    )
    row = aggregate_run("g1", events)
    assert row["kind"] == "guards"
    assert row["scenario"] == "drift"
    assert row["drift_events"] == 1
    assert row["loop_events"] == 0
    assert row["guard_actions"] == "replan"
    assert row["recovered"] is True and row["aborted"] is False


def test_seq_contiguity_detected() -> None:
    ok = aggregate_run("r1", _report_run("r1", supported=2, contradicted=0))
    assert ok["seq_contiguous"] is True
    broken = aggregate_run(
        "r2", [_event("r2", 1, "phase_change", {}), _event("r2", 3, "metric", {"kind": "x"})]
    )
    assert broken["seq_contiguous"] is False


# ---- 跨 run ---- #
def test_aggregate_pools_claim_level_rates() -> None:
    rows = [
        aggregate_run("r1", _report_run("r1", supported=9, contradicted=1)),  # 10 claims
        aggregate_run("r2", _report_run("r2", supported=5, contradicted=0)),  # 5 claims
        aggregate_run(
            "g1",
            _guard_run("g1", scenario="none", code=None, action="", recovered=True, aborted=False),
        ),
    ]
    agg = aggregate_all(rows)
    assert agg["metrics"]["verifiable_claims_total"] == 15
    assert agg["metrics"]["grounding_support_rate"] == round(14 / 15, 4)
    assert agg["metrics"]["false_positive_rate"] == 0.0  # 正常 run 未触发守卫


def test_aggregate_timeout_family_uses_error_events_not_guard_trigger() -> None:
    """timeout 族没有 guard_trigger，必须靠 error 事件判定（否则检出率恒为 0）。"""
    rows = [
        aggregate_run(
            "t1",
            _guard_run(
                "t1",
                scenario="timeout",
                code=None,
                action="",
                recovered=True,
                aborted=False,
                timeout_error=True,
            ),
        ),
        aggregate_run(
            "t2",
            _guard_run(
                "t2",
                scenario="timeout",
                code=None,
                action="",
                recovered=True,
                aborted=False,
                timeout_error=True,
            ),
        ),
    ]
    agg = aggregate_all(rows)
    assert agg["by_fault"]["timeout"]["detection_rate"] == 1.0


def test_aggregate_detection_and_false_positive_rates() -> None:
    rows = [
        aggregate_run(
            "d1",
            _guard_run(
                "d1",
                scenario="drift",
                code="E_GUARD_DRIFT",
                action="replan",
                recovered=True,
                aborted=False,
            ),
        ),
        aggregate_run(
            "d2",
            _guard_run(
                "d2", scenario="drift", code=None, action="", recovered=False, aborted=False
            ),
        ),
        aggregate_run(
            "n1",
            _guard_run("n1", scenario="none", code=None, action="", recovered=True, aborted=False),
        ),
        aggregate_run(
            "n2",
            _guard_run(
                "n2",
                scenario="none",
                code="E_GUARD_DRIFT",
                action="retry",
                recovered=False,
                aborted=False,
            ),
        ),
    ]
    agg = aggregate_all(rows)
    assert agg["by_fault"]["drift"]["detection_rate"] == 0.5
    assert agg["by_fault"]["none"]["detection_rate"] == 0.0
    assert agg["metrics"]["false_positive_rate"] == 0.5  # 2 个正常 run 里 1 个误报


def test_cost_mean_includes_zero_cost_runs_and_reports_max() -> None:
    rows = [
        aggregate_run("r1", _report_run("r1", supported=1, contradicted=0)),  # cost 0.01
        aggregate_run("r2", _report_run("r2", supported=1, contradicted=0)),
    ]
    for row in rows[1:]:
        for _ in _report_run(row["run_id"], supported=1, contradicted=0):
            pass
    rows[1]["cost_usd"] = 0.0  # 模拟缓存命中
    agg = aggregate_all(rows)
    assert agg["metrics"]["cost_usd_mean_per_report"] == 0.005
    assert agg["metrics"]["cost_usd_max_per_report"] == 0.01


def test_select_campaign_keeps_only_latest_runs_per_scenario() -> None:
    by_run: dict[str, list[Event]] = {}
    for idx in range(4):  # 同一场景 4 次历史尝试
        run_id = f"p0-s6-drift-{idx}"
        by_run[run_id] = _guard_run(
            run_id,
            scenario="drift",
            code="E_GUARD_DRIFT",
            action="replan",
            recovered=True,
            aborted=False,
        )
    by_run["p0-s5-a"] = _report_run("p0-s5-a", supported=1, contradicted=0)
    by_run["p0-s5-b"] = _report_run("p0-s5-b", supported=1, contradicted=0)
    by_run["p0-s5-c"] = _report_run("p0-s5-c", supported=1, contradicted=0)

    selected = select_campaign(by_run, last_per_scenario=2, last_reports=1)
    assert len([r for r in selected if r.startswith("p0-s6-drift")]) == 2
    assert len([r for r in selected if r.startswith("p0-s5")]) == 1


def test_empty_events_produce_none_rates() -> None:
    row = aggregate_run("empty", [])
    assert row["grounding_support_rate"] is None
    assert row["hallucination_rate"] is None
    agg = aggregate_all([row])
    assert agg["metrics"]["grounding_support_rate"] is None
    assert agg["metrics"]["false_positive_rate"] is None
