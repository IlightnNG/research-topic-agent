"""Kernel invariants across success/error schedules."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeSpec
from lit_agent_v2.contracts.tool import ToolResult, ToolSpec
from lit_agent_v2.kernel.node.checkpoint import KernelCheckpoint
from lit_agent_v2.kernel.node.loop import Kernel

VALID_STOPS = {"final", "failed", "no_progress", "max_steps", "budget", "cancelled", "timeout"}


@dataclass
class Usage:
    prompt_tokens: int = 1
    completion_tokens: int = 1
    cost_usd: float = 0.0
    model: str = "fake"


class LLM:
    def __init__(self, actions: list[dict]) -> None:
        self.actions = actions
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        action = self.actions[min(self.calls, len(self.actions) - 1)]
        self.calls += 1
        return action, Usage()


class Registry:
    def __init__(self) -> None:
        self.specs = {
            "echo": ToolSpec(
                "echo",
                "echo",
                {"type": "object", "properties": {"q": {"type": "string"}}},
                handler=lambda args: {"value": args.get("q", "")},
            )
        }
        self.called = 0

    def names(self):
        return ["echo"]

    def spec(self, name):
        return self.specs.get(name)

    def call(self, name, args):
        self.called += 1
        return ToolResult(True, {"value": args.get("q", "")})


def _context() -> NodeContext:
    return NodeContext("r1", "n1", "do work", FeatureProfile(), {})


def _node(**kwargs) -> NodeSpec:  # noqa: ANN003
    defaults = {"id": "n1", "goal": "do work", "tools": ("echo",), "max_steps": 4}
    defaults.update(kwargs)
    return NodeSpec(**defaults)


@pytest.mark.parametrize(
    ("actions", "stop"),
    [
        ([{"action": "final", "outputs": {"ok": 1}}], "final"),
        (
            [
                {"action": "tool", "tool": "echo", "args": {"q": "x"}},
                {"action": "final", "outputs": {"ok": 2}},
            ],
            "final",
        ),
        ([{"action": "tool", "tool": "other", "args": {}}], "failed"),
        ([{"action": "tool", "tool": "echo", "args": {}}, {"action": "final", "outputs": {}}], "final"),
        ([{"action": "tool", "tool": "echo", "args": {}}], "no_progress"),
    ],
)
def test_stop_reasons_and_artifacts(actions: list[dict], stop: str) -> None:
    result = Kernel(LLM(actions), Registry()).run(_node(), _context())
    assert result.stop_reason in VALID_STOPS
    assert result.stop_reason == stop or stop == "no_progress"
    assert isinstance(result.output, dict)
    assert isinstance(result.usage, dict)
    assert result.checkpoint["journal"]
    kinds = [entry["kind"] for entry in result.checkpoint["journal"]]
    assert kinds[0] == "turn.started"
    assert kinds[-1] == "kernel.finished"
    if result.stop_reason == "final":
        assert "assistant.final" in kinds


def test_trace_call_ids_are_unique_and_paired() -> None:
    actions = [
        {
            "action": "tool",
            "calls": [
                {"id": "a", "name": "echo", "args": {"q": "1"}},
                {"id": "b", "name": "echo", "args": {"q": "2"}},
            ],
        },
        {"action": "final", "outputs": {"ok": True}},
    ]
    result = Kernel(LLM(actions), Registry()).run(_node(), _context())
    ids = [entry["call_id"] for entry in result.trace]
    assert ids == ["a", "b"]
    assert len(ids) == len(set(ids))
    assert all(entry["ok"] for entry in result.trace)


def test_checkpoint_roundtrip() -> None:
    result = Kernel(
        LLM([{"action": "tool", "tool": "echo", "args": {"q": "x"}}, {"action": "final", "outputs": {}}]),
        Registry(),
    ).run(_node(), _context())
    state = KernelCheckpoint.from_dict(result.checkpoint)
    assert state.node_id == "n1"
    assert state.trace == result.trace
    assert state.journal == result.checkpoint["journal"]
    assert state.stop_reason == "final"


def test_max_steps_never_exceeds_schedule() -> None:
    actions = [{"action": "tool", "tool": "echo", "args": {"q": str(i)}} for i in range(10)]
    result = Kernel(LLM(actions), Registry()).run(_node(max_steps=2), _context())
    assert result.stop_reason == "max_steps"
    assert len(result.trace) == 2
