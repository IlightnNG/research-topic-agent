"""3.2 / S10–S12 验收：analysis L2 逐条校验-修复，默认不变。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.config import Settings
from lit_agent.eval.faultinject import inject
from lit_agent.graph.nodes import Phase2Nodes
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation
from lit_agent.runtime.graph_runner import run_graph


def enable_l2(settings: Settings) -> Settings:
    pipeline = settings.pipeline.model_copy(update={"analysis_l2": True})
    return settings.model_copy(update={"pipeline": pipeline})


def tool_names(settings: Settings, run_id: str) -> list[str]:
    return [
        str(event["payload"].get("tool"))
        for event in fetch_events(settings, run_id)
        if event["type"] == "tool_call"
    ]


def test_default_is_l1(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    out = run_graph(settings, "ai-agents", run_id="a-l1", focus_hint="tool use")

    assert out["state"] == "succeeded"
    assert not out["stages"].get("analysis_l2")
    assert tool_names(settings, "a-l1") == []


def test_l2_verifies_each_claim(tmp_path: Path) -> None:
    settings = enable_l2(prepare(tmp_path, papers=2))
    out = run_graph(settings, "ai-agents", run_id="a-l2", focus_hint="tool use")

    stages = out["stages"]
    assert stages["analysis_l2"] is True
    assert stages["repair"]["claims_verified"] == stages["claims"]
    assert stages["repair"]["claims_rewritten"] == 0
    assert stages["repair"]["claims_dropped"] == 0
    assert tool_names(settings, "a-l2").count("verify_claim") == stages["claims"]


def test_l2_drops_unfixable_claim(tmp_path: Path) -> None:
    settings = enable_l2(prepare(tmp_path, papers=3))
    with inject("bad_artifact"):
        out = run_graph(settings, "ai-agents", run_id="a-l2b", focus_hint="tool use")

    stages = out["stages"]
    assert out["state"] == "succeeded"
    assert stages["repair"]["claims_dropped"] == 1
    assert stages["claims"] == 2  # 3 条里丢掉 1 条
    assert stages["grounding_rate"] == 1.0


def test_rewrite_turns_unsupported_into_supported(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=1)
    node = Phase2Nodes(settings)
    claims = [
        Claim(
            text="quantum chromodynamics explains superconductivity",
            citations=[Citation(paper_id="P0", snippet="tool use improves task success.")],
        )
    ]
    kept, repair = node._analysis_l2(claims)

    assert len(kept) == 1
    assert repair["claims_rewritten"] == 1
    assert repair["claims_dropped"] == 0
    assert kept[0].text != claims[0].text
    assert "tool use" in kept[0].text.lower()


def test_claim_tools_are_registered() -> None:
    from lit_agent.tools.spec import DEFAULT_TOOL_SPECS, TOOL_IMPLEMENTATIONS

    assert {"extract_claims", "verify_claim", "rewrite_claim"} <= set(DEFAULT_TOOL_SPECS)
    assert {"extract_claims", "verify_claim", "rewrite_claim"} <= set(TOOL_IMPLEMENTATIONS)
