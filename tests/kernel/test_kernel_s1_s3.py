"""3.4 / S1-S3: workflow spec, kernel tools and bounded loop."""

from __future__ import annotations

import json

from lit_agent.kernel.runtime import Kernel
from lit_agent.kernel.tools import KernelTools
from lit_agent.kernel.types import KernelGoal
from lit_agent.models.evidence import EvidenceCard
from lit_agent.workflow.spec import NodeSpec, WorkflowSpec, validate_workflow


def _cards() -> list[EvidenceCard]:
    return [
        EvidenceCard(
            paper_id="P1",
            title="Tool use in agents",
            snippet="tool use improves task success",
            source="test",
        )
    ]


def test_workflow_spec_is_static_and_serializable() -> None:
    spec = WorkflowSpec(
        name="demo",
        nodes=(
            NodeSpec(id="a", kind="deterministic", goal="a", output_key="a_out"),
            NodeSpec(
                id="b",
                kind="agent",
                goal="b",
                input_keys=("a_out",),
                output_key="b_out",
                allowed_tools=("search_topic",),
            ),
        ),
    )
    assert validate_workflow(spec) == []
    payload = json.dumps(spec.to_dict())
    assert '"name": "demo"' in payload


def test_workflow_validation_rejects_bad_order_and_duplicates() -> None:
    spec = WorkflowSpec(
        name="bad",
        nodes=(
            NodeSpec(id="a", kind="deterministic", goal="a", output_key="a_out"),
            NodeSpec(
                id="a",
                kind="agent",
                goal="b",
                input_keys=("missing",),
                allowed_tools=(),
            ),
        ),
    )
    problems = validate_workflow(spec)
    assert any("duplicate" in item for item in problems)
    assert any("needs allowed_tools" in item for item in problems)
    assert any("input not produced" in item for item in problems)


def test_kernel_tools_search_and_events() -> None:
    events: list[dict] = []
    tools = KernelTools.from_cards(_cards(), event_sink=events.append)
    result = tools.call("search_topic", {"query": "tool use", "k": 3})

    assert result.ok
    assert result.output["paper_ids"] == ["P1"]
    assert [item["event"] for item in events] == ["tool.called", "tool.result"]


class FakeTools:
    def __init__(self, *, cost: float = 0.0) -> None:
        self.calls = 0
        self.cost = cost

    def names(self) -> list[str]:
        return ["echo"]

    def spec(self, name: str):
        class S:
            description = "echo"
            parameters = {"x": "number"}

        return S()

    def call(self, name: str, args: dict):
        self.calls += 1

        class R:
            ok = True
            output = {"x": args.get("x")}
            error_code = None
            meta = {"cost_usd": self.cost}

        return R()


def test_kernel_tool_then_final() -> None:
    replies = [
        {"action": "tool", "tool": "echo", "args": {"x": 1}},
        {"action": "final", "outputs": {"value": 2}},
    ]
    kernel = Kernel(tools=FakeTools())

    def completer(_history, _goal):
        return replies.pop(0)

    result = kernel.run(
        KernelGoal(node_id="n1", objective="do", allowed_tools=("echo",), max_steps=3),
        completer=completer,
    )
    assert result.stop_reason == "final"
    assert result.output == {"value": 2}
    assert result.steps_used == 2
    assert [item.name for item in result.trace] == ["echo"]


def test_kernel_max_steps() -> None:
    kernel = Kernel(tools=FakeTools())
    result = kernel.run(
        KernelGoal(node_id="n1", objective="loop", allowed_tools=("echo",), max_steps=2),
        completer=lambda _h, _g: {"action": "tool", "tool": "echo", "args": {"x": 1}},
    )
    assert result.stop_reason == "max_steps"
    assert result.steps_used == 2


def test_kernel_rejects_unallowed_tool() -> None:
    kernel = Kernel(tools=FakeTools())
    result = kernel.run(
        KernelGoal(node_id="n1", objective="x", allowed_tools=("echo",)),
        completer=lambda _h, _g: {"action": "tool", "tool": "other", "args": {}},
    )
    assert result.stop_reason == "failed"
    assert result.trace[0].error_code == "E_TOOL_NOT_ALLOWED"


def test_kernel_cancel_and_no_progress() -> None:
    kernel = Kernel(tools=FakeTools())
    kernel.cancel()
    cancelled = kernel.run(
        KernelGoal(node_id="n1", objective="x", allowed_tools=("echo",)),
        completer=lambda _h, _g: {"action": "final", "outputs": {"ok": True}},
    )
    assert cancelled.stop_reason == "cancelled"

    kernel = Kernel(tools=FakeTools())
    stopped = kernel.run(
        KernelGoal(node_id="n2", objective="x", allowed_tools=("echo",), max_steps=4),
        completer=lambda _h, _g: {"action": "tool", "tool": "echo", "args": {"x": 1}},
    )
    assert stopped.stop_reason == "no_progress"


def test_kernel_budget_stops() -> None:
    kernel = Kernel(tools=FakeTools(cost=0.2))
    result = kernel.run(
        KernelGoal(
            node_id="n1",
            objective="cost",
            allowed_tools=("echo",),
            max_steps=4,
            max_usd=0.05,
        ),
        completer=lambda _h, _g: {"action": "tool", "tool": "echo", "args": {"x": 1}},
    )
    assert result.stop_reason == "budget"
    assert result.cost_usd >= 0.2
