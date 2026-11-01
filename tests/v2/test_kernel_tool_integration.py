"""Kernel + ToolRegistry + WorkflowRunner integration tests."""

from __future__ import annotations

from dataclasses import dataclass

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.kernel.node.loop import Kernel
from lit_agent_v2.tools.packs.claims import build_claim_tools
from lit_agent_v2.tools.packs.corpus import build_corpus_tools
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.workflow.node.runner import WorkflowRunner


@dataclass
class Usage:
    prompt_tokens: int = 3
    completion_tokens: int = 2
    cost_usd: float = 0.0
    model: str = "fake"


class RoutingLLM:
    def __init__(self, actions: dict[str, list[dict]]) -> None:
        self.actions = actions
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        system = messages[0]["content"]
        node_id = next(line.split("Node: ", 1)[1] for line in system.splitlines() if line.startswith("Node: "))
        sequence = self.actions[node_id]
        action = sequence[min(self.calls, len(sequence) - 1)]
        self.calls += 1
        return action, Usage()


class AcceptVerifier:
    def verify(self, node: NodeSpec, context: NodeContext, result: NodeResult) -> Verdict:
        return Verdict(True)


class Store:
    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.outputs: dict[str, dict] = {}

    def state(self, run_id: str, node_id: str) -> str | None:
        return self.states.get(node_id)

    def load_output(self, run_id: str, node_id: str) -> dict | None:
        return self.outputs.get(node_id)

    def commit(self, run_id: str, node_id: str, output: dict, verdict: Verdict) -> None:
        self.states[node_id] = "committed"
        self.outputs[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        self.states[node_id] = "degraded"


def _node(node_id: str, tools: tuple[str, ...], inputs: tuple[str, ...] = ()) -> NodeSpec:
    return NodeSpec(node_id, f"do {node_id}", tools, inputs=inputs, max_steps=4)


def _echo_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            "echo",
            "echo",
            {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
            handler=lambda args: {"value": args["q"]},
        )
    ]


def test_workflow_kernel_and_tool_registry() -> None:
    registry = ToolRegistry(_echo_tools())
    llm = RoutingLLM(
        {
            "a": [
                {"action": "tool", "calls": [{"id": "a1", "name": "echo", "args": {"q": "A"}}]},
                {"action": "final", "outputs": {"value": "A"}},
            ],
            "b": [
                {"action": "tool", "calls": [{"id": "b1", "name": "echo", "args": {"q": "B"}}]},
                {"action": "final", "outputs": {"value": "B"}},
            ],
        }
    )
    kernel = Kernel(llm, registry)
    store = Store()
    workflow = WorkflowDefinition(
        "t",
        "1",
        (_node("a", ("echo",)), _node("b", ("echo",), ("a",))),
    )
    outputs = WorkflowRunner(kernel=kernel, verifier=AcceptVerifier(), store=store).run(
        workflow, run_id="r1", inputs={"request": {}}
    )
    assert outputs["a"]["value"] == "A"
    assert outputs["b"]["value"] == "B"
    assert store.states == {"a": "committed", "b": "committed"}


def test_corpus_and_claims_tools_through_kernel(tmp_path) -> None:  # noqa: ANN001
    registry = ToolRegistry(build_corpus_tools() + build_claim_tools())
    llm = RoutingLLM(
        {
            "n1": [
                {
                    "action": "tool",
                    "calls": [
                        {"id": "c1", "name": "corpus.stats", "args": {"root": str(tmp_path)}},
                        {
                            "id": "c2",
                            "name": "claims.extract",
                            "args": {
                                "paper_id": "P1",
                                "text": "We find that tool use improves agent success on benchmark tasks.",
                            },
                        },
                    ],
                },
                {"action": "final", "outputs": {"done": True}},
            ]
        }
    )
    (tmp_path / "papers.jsonl").write_text(
        '{"paper_id":"P1","title":"T","abstract":"x"}\n', encoding="utf-8"
    )
    context = NodeContext("r1", "n1", "inspect", FeatureProfile(), {})
    result = Kernel(llm, registry).run(_node("n1", ("corpus.stats", "claims.extract")), context)
    assert result.stop_reason == "final"
    assert len(result.trace) == 2
    assert result.trace[0]["tool"] == "corpus.stats"
    assert result.trace[1]["tool"] == "claims.extract"


def test_schema_error_does_not_end_turn() -> None:
    registry = ToolRegistry(_echo_tools())
    llm = RoutingLLM(
        {
            "n1": [
                {"action": "tool", "calls": [{"id": "x", "name": "echo", "args": {}}]},
                {"action": "final", "outputs": {"ok": True}},
            ]
        }
    )
    result = Kernel(llm, registry).run(
        _node("n1", ("echo",)), NodeContext("r1", "n1", "x", FeatureProfile(), {})
    )
    assert result.stop_reason == "final"
    assert result.trace[0]["ok"] is False
    assert result.trace[0]["error"] == "E_TOOL_SCHEMA"


def test_tool_timeout_is_an_observation() -> None:
    import time

    registry = ToolRegistry(
        [
            ToolSpec(
                "slow",
                "slow",
                timeout_s=0.01,
                max_retries=0,
                handler=lambda _args: (time.sleep(0.05), {})[1],
            )
        ]
    )
    llm = RoutingLLM(
        {
            "n1": [
                {"action": "tool", "calls": [{"id": "s1", "name": "slow", "args": {}}]},
                {"action": "final", "outputs": {"ok": True}},
            ]
        }
    )
    result = Kernel(llm, registry).run(
        _node("n1", ("slow",)), NodeContext("r1", "n1", "x", FeatureProfile(), {})
    )
    assert result.stop_reason == "final"
    assert result.trace[0]["error"] == "E_TOOL_TIMEOUT"


def test_side_effect_call_serializes_group() -> None:
    import time

    order: list[str] = []

    def read(_args):
        time.sleep(0.05)
        order.append("echo")
        return {}

    def write(_args):
        order.append("write")
        return {}

    registry = ToolRegistry(
        [
            ToolSpec("echo", "read", handler=read),
            ToolSpec("write", "write", side_effect=True, handler=write),
        ]
    )
    llm = RoutingLLM(
        {
            "n1": [
                {
                    "action": "tool",
                    "calls": [
                        {"id": "r", "name": "echo", "args": {}},
                        {"id": "w", "name": "write", "args": {}},
                    ],
                },
                {"action": "final", "outputs": {}},
            ]
        }
    )
    Kernel(llm, registry).run(
        _node("n1", ("echo", "write")),
        NodeContext("r1", "n1", "x", FeatureProfile(), {}),
    )
    assert order == ["echo", "write"]
