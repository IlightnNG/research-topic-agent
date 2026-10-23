"""S1 验收：pipeline 配置体系（默认等价、env 覆盖、非法值拒绝、行为生效）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.config import (
    GateSettings,
    LimitSettings,
    PipelineSettings,
    Settings,
    load_settings,
)
from lit_agent.errors import E_CONFIG_INVALID, LitError
from lit_agent.eval import faultinject
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import fetch_events, prepare


def test_defaults_equal_phase_2_1_behaviour() -> None:
    settings = Settings()
    pipeline = settings.pipeline
    assert pipeline.gates.enabled is True
    assert pipeline.gates.evidence_min_cards == 1  # 与现状等价（生产建议 3）
    assert pipeline.gates.support_ratio_min == 0.6
    assert pipeline.limits.max_attempts == {"analysis": 2, "retrieval": 2, "report": 1}
    assert pipeline.limits.max_total_llm_calls == 12
    assert pipeline.limits.recursion_limit == 60
    assert pipeline.limits.max_run_usd == 2.0
    assert pipeline.transitions is True
    assert pipeline.hybrid_alpha == 0.6
    assert pipeline.pdf_enabled is False
    assert pipeline.llm == "auto"


def test_env_override_works() -> None:
    settings = load_settings(
        environ={
            "LIT_AGENT_PIPELINE__GATES__EVIDENCE_MIN_CARDS": "3",
            "LIT_AGENT_PIPELINE__TRANSITIONS": "false",
            "LIT_AGENT_PIPELINE__LLM": "off",
            "LIT_AGENT_PIPELINE__LIMITS__MAX_TOTAL_LLM_CALLS": "5",
        }
    )
    assert settings.pipeline.gates.evidence_min_cards == 3
    assert settings.pipeline.transitions is False
    assert settings.pipeline.llm == "off"
    assert settings.pipeline.limits.max_total_llm_calls == 5


def test_invalid_value_is_rejected_at_load() -> None:
    with pytest.raises(LitError) as excinfo:
        load_settings(environ={"LIT_AGENT_PIPELINE__GATES__EVIDENCE_MIN_CARDS": "0"})
    assert excinfo.value.code == E_CONFIG_INVALID

    with pytest.raises(LitError):
        load_settings(environ={"LIT_AGENT_PIPELINE__LLM": "always"})


def _settings(tmp_path: Path, pipeline: PipelineSettings) -> Settings:
    base = prepare(tmp_path)
    return base.model_copy(update={"pipeline": pipeline})


def test_gates_can_be_disabled(tmp_path: Path) -> None:
    settings = _settings(tmp_path, PipelineSettings(gates=GateSettings(enabled=False)))

    with faultinject.inject("bad_artifact"):
        result = run_graph(settings, "ai-agents", run_id="cfg-off")
    assert result["state"] == "succeeded"

    # 关的是"门禁"；守卫（G9 引用完整性）仍会独立报警，因此断言门禁结果为空
    gate_results = [
        event["payload"].get("gates")
        for event in fetch_events(settings, "cfg-off")
        if event["type"] == "phase_change"
        and event["payload"].get("phase") == "end"
        and event["payload"].get("gates")
    ]
    assert gate_results == [], gate_results


def test_attempt_limit_comes_from_config(tmp_path: Path) -> None:
    """analysis 只允许 1 次 → 坏产物直接降级，不产生 recovery 回边。"""
    pipeline = PipelineSettings(
        limits=LimitSettings(max_attempts={"analysis": 1, "retrieval": 2, "report": 1})
    )
    settings = _settings(tmp_path, pipeline)

    with faultinject.inject("bad_artifact"):
        result = run_graph(settings, "ai-agents", run_id="cfg-attempt")

    assert result["state"] == "succeeded"
    events = fetch_events(settings, "cfg-attempt")
    assert not [event for event in events if event["type"] == "recovery"]


def test_pdf_enabled_comes_from_config(tmp_path: Path) -> None:
    settings = _settings(tmp_path, PipelineSettings(pdf_enabled=True))
    cache = Path(settings.storage.data_root) / "pdf_texts"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "P0.txt").write_text("Agents use tools. " * 40, encoding="utf-8")

    run_graph(settings, "ai-agents", run_id="cfg-pdf")

    events = fetch_events(settings, "cfg-pdf")
    assert any(event["type"] == "tool_call" for event in events)
