"""S3 验收：证据阈值（`selected < evidence_min_cards`）的完整行为矩阵。"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.wiring import fetch_events, prepare

from lit_agent.config import GateSettings, LimitSettings, PipelineSettings
from lit_agent.graph import gates as gates_mod
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.context import RunContext
from lit_agent.runtime.graph_runner import run_graph


def _ctx(tmp_path: Path, *, min_cards: int) -> RunContext:
    settings = prepare(tmp_path, papers=1)
    settings = settings.model_copy(
        update={"pipeline": PipelineSettings(gates=GateSettings(evidence_min_cards=min_cards))}
    )
    return RunContext(
        settings=settings,
        run_id="ev",
        topic_id="ai-agents",
        budget=RunBudget(),
    )


# --------------------------------------------------------------------------- #
# 门禁单测：0 / 1 / 3 与阈值 1 / 3
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("selected", "min_cards", "should_fail"),
    [
        (0, 1, True),
        (1, 1, False),
        (1, 3, True),
        (2, 3, True),
        (3, 3, False),
    ],
)
def test_threshold_matrix(tmp_path: Path, selected: int, min_cards: int, should_fail: bool) -> None:
    ctx = _ctx(tmp_path, min_cards=min_cards)
    patch = {"counters": {"selected": selected}}
    result = gates_mod.gate_evidence_sufficiency("retrieval", patch, {}, ctx)
    assert (result is not None) is should_fail
    if result is not None:
        assert result.details["selected"] == selected
        assert result.details["min_cards"] == min_cards
        assert result.details["repair_target"] == "retrieval"


def test_missing_selected_is_not_a_failure(tmp_path: Path) -> None:
    """阶段没跑（无 selected 键）不得误报。"""
    ctx = _ctx(tmp_path, min_cards=3)
    assert gates_mod.gate_evidence_sufficiency("retrieval", {"counters": {}}, {}, ctx) is None


# --------------------------------------------------------------------------- #
# 集成：阈值 3 + 1 篇论文 → 回边一次 → 仍不足 → 降级（不中止）
# --------------------------------------------------------------------------- #
def test_threshold_three_repairs_once_then_degrades(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=1)
    settings = settings.model_copy(
        update={
            "pipeline": PipelineSettings(
                gates=GateSettings(evidence_min_cards=3),
                limits=LimitSettings(max_attempts={"analysis": 2, "retrieval": 2, "report": 1}),
            )
        }
    )

    result = run_graph(settings, "ai-agents", run_id="ev-3")
    assert result["state"] == "succeeded", result

    events = fetch_events(settings, "ev-3")
    attempts = [
        event["payload"].get("attempt")
        for event in events
        if event["type"] == "phase_change"
        and event["stage"] == "retrieval"
        and event["payload"].get("phase") == "start"
    ]
    assert attempts == [1, 2], f"retrieval 应恰好回边一次：{attempts}"

    codes = {
        event["payload"].get("code")
        for event in events
        if event["type"] == "guard_trigger"
    }
    assert "E_GROUND_NO_EVIDENCE" in codes, codes


def test_threshold_one_no_repair(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=1)
    settings = settings.model_copy(
        update={"pipeline": PipelineSettings(gates=GateSettings(evidence_min_cards=1))}
    )

    result = run_graph(settings, "ai-agents", run_id="ev-1")
    assert result["state"] == "succeeded"

    events = fetch_events(settings, "ev-1")
    attempts = [
        event["payload"].get("attempt")
        for event in events
        if event["type"] == "phase_change"
        and event["stage"] == "retrieval"
        and event["payload"].get("phase") == "start"
    ]
    assert attempts == [1], attempts
