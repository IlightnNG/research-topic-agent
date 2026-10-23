"""S4 验收：漂移产出者（scope ↔ 产出覆盖率）+ 门禁拦截 + 健康 run 零误报。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.config import GateSettings, PipelineSettings
from lit_agent.eval.scope_drift import drift_for
from lit_agent.runtime.graph_runner import run_graph


# --------------------------------------------------------------------------- #
# 纯函数：ok / warn / block / 短 scope 不判定 / 空产出不算漂移
# --------------------------------------------------------------------------- #
def test_ok_when_claims_cover_scope() -> None:
    assert drift_for("tool use agents", ["Tool use improves task success"]).verdict == "ok"


def test_block_when_totally_unrelated() -> None:
    coverage = drift_for(
        "protein folding cryo microscopy thermodynamics",
        ["Tool use improves task success in agent systems"],
    )
    assert coverage.verdict == "block"


def test_warn_between_thresholds() -> None:
    scope = "alpha beta gamma delta epsilon zeta theta iota kappa lambda"
    result = drift_for(scope, ["alpha only"])
    assert 0.05 <= result.coverage < 0.15, result
    assert result.verdict == "warn"


def test_short_scope_is_not_judged() -> None:
    assert drift_for("agents", ["protein folding"]).verdict == "ok"


def test_empty_claims_is_not_drift() -> None:
    assert drift_for("protein folding microscopy", []).verdict == "ok"


def test_thresholds_are_configurable() -> None:
    scope = "alpha beta gamma delta epsilon zeta theta iota kappa lambda"
    strict = drift_for(scope, ["alpha only"], warn_below=0.2, block_below=0.05)
    loose = drift_for(scope, ["alpha only"], warn_below=0.05, block_below=0.01)
    assert strict.verdict == "warn"
    assert loose.verdict == "ok"


# --------------------------------------------------------------------------- #
# 集成：真跑题 → 门禁 abort；正常 scope → 零告警
# --------------------------------------------------------------------------- #
def test_drift_aborts_run(tmp_path: Path) -> None:
    settings = prepare(
        tmp_path,
        specs=[("Tool use agents", "tool use improves task success")],
        scope="protein folding cryo microscopy thermodynamics",
    )
    settings = settings.model_copy(
        update={"pipeline": PipelineSettings(gates=GateSettings(evidence_min_cards=1))}
    )

    result = run_graph(settings, "ai-agents", run_id="drift-1")
    assert result["state"] == "aborted", result
    assert result["error_code"] == "E_GUARD_DRIFT"

    events = fetch_events(settings, "drift-1")
    aborts = [
        event["payload"]
        for event in events
        if event["type"] == "guard_trigger"
        and event["payload"].get("code") == "E_GUARD_DRIFT"
    ]
    assert aborts, "漂移必须留下 guard_trigger"
    assert aborts[-1].get("gate") == "drift", aborts[-1]


def test_healthy_scope_has_no_drift(tmp_path: Path) -> None:
    settings = prepare(
        tmp_path,
        specs=[("Tool use agents", "tool use improves task success")],
        scope="tool use agents",
    )
    settings = settings.model_copy(
        update={"pipeline": PipelineSettings(gates=GateSettings(evidence_min_cards=1))}
    )

    result = run_graph(settings, "ai-agents", run_id="drift-ok")
    assert result["state"] == "succeeded", result

    stages = result.get("stages") or {}
    assert stages.get("drift_verdict") == "ok", stages

    events = fetch_events(settings, "drift-ok")
    warn_or_block = [
        event
        for event in events
        if event["type"] == "guard_trigger"
        and event["payload"].get("code") == "E_GUARD_DRIFT"
    ]
    assert warn_or_block == [], warn_or_block
