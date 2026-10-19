"""Step 1.12–1.14 上层验收：reporter / 上下文预算与折叠 / 槽位 / 工具注册表。"""

from __future__ import annotations

import pytest

from lit_agent.agents.reporter import build_report
from lit_agent.context.budget import fit_many, fit_text
from lit_agent.context.folding import TruncateFolding, folding_for
from lit_agent.context.slots import CtxSlot, SlotRegistry
from lit_agent.errors import LitError
from lit_agent.models.evidence import EvidenceCard
from lit_agent.models.evidence import Support as _UnusedSupport  # noqa: F401
from lit_agent.tools import builtin
from lit_agent.tools.registry import Tool, ToolRegistry


def cards() -> list[EvidenceCard]:
    return [
        EvidenceCard(
            paper_id="W2", title="Tools", snippet="agents use tools", source="openalex", year=2025
        ),
        EvidenceCard(
            paper_id="W1",
            title="Planners",
            snippet="planning improves",
            source="openalex",
            year=2024,
        ),
    ]


# --------------------------------------------------------------------------- #
# reporter
# --------------------------------------------------------------------------- #
def test_report_is_deterministic_and_cited() -> None:
    first = build_report(cards(), topic_id="ai-agents", run_id="r1")
    second = build_report(list(reversed(cards())), topic_id="ai-agents", run_id="r1")

    assert first.content_md == second.content_md, "排序必须确定，否则 D4 幂等失效"
    assert first.content_sha == second.content_sha
    assert first.n_claims == 2
    assert all(claim.citations for claim in first.claims), "每条 claim 必须带引用"


def test_report_without_evidence_is_explicitly_unsupported() -> None:
    report = build_report([], topic_id="t", run_id="r0")
    assert report.n_claims == 1
    assert report.claims[0].support.value == "unsupported"
    assert report.claims[0].citations == []


# --------------------------------------------------------------------------- #
# context budget / folding
# --------------------------------------------------------------------------- #
def test_fit_text_keeps_within_budget() -> None:
    text = " ".join(f"Sentence {index} about agents and tools." for index in range(40))
    result = fit_text(text, budget_tokens=40)
    assert result.truncated is True
    assert result.tokens <= 40
    assert result.text


def test_fit_text_passthrough_when_small() -> None:
    result = fit_text("short text", budget_tokens=100)
    assert result.truncated is False
    assert result.text == "short text"


def test_fit_many_respects_total_budget() -> None:
    texts = ["a " * 200, "b " * 200]
    result = fit_many(texts, budget_tokens=30)
    assert result.tokens <= 30
    assert result.truncated is True


def test_truncate_folding_and_unimplemented_strategies() -> None:
    folding = TruncateFolding()
    assert folding.fold(["x " * 300], budget_tokens=25).tokens <= 25

    with pytest.raises(LitError) as excinfo:
        folding_for("summarize")
    assert excinfo.value.code == "E_FEATURE_DISABLED"


# --------------------------------------------------------------------------- #
# slots
# --------------------------------------------------------------------------- #
def test_slot_registry_rejects_duplicates_and_unknown() -> None:
    registry = SlotRegistry()
    registry.register(CtxSlot(name="scope", content="llm agents", priority=3))
    registry.register(CtxSlot(name="evidence", content="[1] ...", priority=1))

    with pytest.raises(LitError):
        registry.register(CtxSlot(name="scope", content="dup"))
    with pytest.raises(LitError):
        registry.register(CtxSlot(name="bogus", content="x"))

    rendered = registry.render()
    assert rendered.index("llm agents") < rendered.index("[1]")


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #
def test_tool_registry_duplicate_and_unknown() -> None:
    registry = ToolRegistry()
    registry.register(Tool(name="echo", run=lambda **kwargs: kwargs.get("value")))

    assert registry.list_tools() == ["echo"]
    assert registry.call("echo", value=3).output == 3

    with pytest.raises(LitError):
        registry.register(Tool(name="echo", run=lambda **kwargs: None))
    with pytest.raises(LitError):
        registry.get("missing")


def test_tool_failure_becomes_structured_result() -> None:
    def boom(**kwargs):
        raise RuntimeError("tool exploded")

    registry = ToolRegistry()
    registry.register(Tool(name="boom", run=boom))
    result = registry.call("boom")
    assert result.ok is False
    assert result.error_code == "E_UNEXPECTED"


def test_kv_cache_tool_roundtrip() -> None:
    tool = builtin.kv_cache.build_tool()
    assert tool(action="put", key="k", value={"a": 1}).output is True
    assert tool(action="get", key="k").output == {"a": 1}
    assert tool(action="clear").output is True
    assert tool(action="get", key="k").output is None


def test_openalex_search_tool_is_registered_shape() -> None:
    tool = builtin.openalex_search.build_tool()
    assert tool.name == "openalex_search"
    assert tool.timeout_s > 0
    assert "selector" in tool.parameters
