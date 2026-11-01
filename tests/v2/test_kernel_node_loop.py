"""Phase 4.1.3: Node kernel ReAct, tools, budget, checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeSpec
from lit_agent_v2.contracts.tool import ToolResult, ToolSpec
from lit_agent_v2.kernel.node.checkpoint import KernelCheckpoint
from lit_agent_v2.kernel.node.loop import Kernel


@dataclass
class Usage:
    prompt_tokens: int = 10
    completion_tokens: int = 5
    cost_usd: float = 0.01
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
        self.called: list[tuple[str, dict]] = []
        self._specs = {
            "echo": ToolSpec(
                "echo",
                "echo args",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                handler=lambda args: {"echo": args},
            ),
            "big": ToolSpec(
                "big",
                "large output",
                handler=lambda args: {"text": "x" * 1000},
            ),
            "write": ToolSpec(
                "write",
                "side effect",
                side_effect=True,
                handler=lambda args: {"written": args.get("n", 0)},
            )
        }

    def names(self) -> list[str]:
        return sorted(self._specs)

    def spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        self.called.append((name, args))
        spec = self._specs[name]
        return ToolResult(True, spec.handler(args) if spec.handler else {})


class Checkpoints:
    def __init__(self) -> None:
        self.saved: dict[str, dict] = {}

    def save(self, run_id: str, node_id: str, checkpoint: dict[str, Any]) -> None:
        self.saved[node_id] = checkpoint

    def load(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        return self.saved.get(node_id)


def _node(**kwargs) -> NodeSpec:  # noqa: ANN003
    defaults = {"id": "n1", "goal": "do work", "tools": ("echo",), "max_steps": 4}
    defaults.update(kwargs)
    return NodeSpec(**defaults)


def _context() -> NodeContext:
    return NodeContext("r1", "n1", "do work", FeatureProfile(), {})


def test_tool_then_final_and_checkpoint() -> None:
    llm = LLM(
        [
            {"action": "tool", "tool": "echo", "args": {"q": "x"}},
            {"action": "final", "outputs": {"ok": True}},
        ]
    )
    registry = Registry()
    checkpoints = Checkpoints()
    kernel = Kernel(llm, registry, checkpoint_store=checkpoints)
    result = kernel.run(_node(), _context())
    assert result.stop_reason == "final"
    assert result.output == {"ok": True}
    assert registry.called == [("echo", {"q": "x"})]
    assert result.usage["prompt_tokens"] == 20
    assert checkpoints.saved["n1"]["stop_reason"] == "final"


def test_multiple_calls_in_one_step() -> None:
    llm = LLM(
        [
            {
                "action": "tool",
                "calls": [
                    {"id": "a", "name": "echo", "args": {"q": 1}},
                    {"id": "b", "name": "echo", "args": {"q": 2}},
                ],
            },
            {"action": "final", "outputs": {"ok": True}},
        ]
    )
    registry = Registry()
    result = Kernel(llm, registry).run(_node(), _context())
    assert result.stop_reason == "final"
    assert registry.called == [("echo", {"q": 1}), ("echo", {"q": 2})]
    assert len(result.trace) == 2


def test_tool_output_is_pruned() -> None:
    kernel = Kernel(
        LLM(
            [
                {"action": "tool", "calls": [{"name": "big", "args": {}}]},
                {"action": "final", "outputs": {"ok": True}},
            ]
        ),
        Registry(),
        max_tool_chars=256,
    )
    result = kernel.run(_node(tools=("big",)), _context())
    tool_entry = next(item for item in result.checkpoint["history"] if item.get("role") == "tool")
    assert tool_entry["output"]["truncated"] is True


def test_retryable_llm_error() -> None:
    class RetryOnce:
        def __init__(self):
            self.calls = 0

        def chat_json(self, messages, **kwargs):  # noqa: ANN001
            self.calls += 1
            if self.calls == 1:
                raise type("Retryable", (RuntimeError,), {"retryable": True})()
            return {"action": "final", "outputs": {"ok": True}}, Usage()

    llm = RetryOnce()
    result = Kernel(llm, Registry(), max_retries=1).run(_node(), _context())
    assert result.stop_reason == "final"
    assert llm.calls == 2


def test_unauthorized_tool_fails() -> None:
    kernel = Kernel(LLM([{"action": "tool", "tool": "other", "args": {}}]), Registry())
    result = kernel.run(_node(), _context())
    assert result.stop_reason == "failed"
    assert result.output == {}


def test_budget_and_no_progress() -> None:
    budget = Kernel(
        LLM([{"action": "tool", "tool": "echo", "args": {"q": "x"}}]),
        Registry(),
    ).run(_node(max_steps=4, max_usd=0.001), _context())
    assert budget.stop_reason == "budget"

    repeated = Kernel(
        LLM(
            [
                {"action": "tool", "tool": "echo", "args": {"q": "x"}},
                {"action": "tool", "tool": "echo", "args": {"q": "x"}},
            ]
        ),
        Registry(),
    ).run(_node(max_steps=4), _context())
    assert repeated.stop_reason == "no_progress"


def test_max_steps_and_cancel() -> None:
    maxed = Kernel(
        LLM([{"action": "tool", "tool": "echo", "args": {"q": str(i)}} for i in range(4)]),
        Registry(),
    ).run(_node(max_steps=2), _context())
    assert maxed.stop_reason == "max_steps"

    cancelled = Kernel(LLM([{"action": "final", "outputs": {}}]), Registry()).run(
        _node(), _context(), should_stop=lambda: True
    )
    assert cancelled.stop_reason == "cancelled"


def test_resume_checkpoint() -> None:
    state = KernelCheckpoint(node_id="n1", step=1, cost_usd=0.02, usage={"prompt_tokens": 10})
    kernel = Kernel(
        LLM([{"action": "final", "outputs": {"resumed": True}}]),
        Registry(),
        checkpoint_store=Checkpoints(),
    )
    result = kernel.run(_node(), _context(), checkpoint=state)
    assert result.stop_reason == "final"
    assert result.output["resumed"] is True
    assert result.usage["prompt_tokens"] == 20
