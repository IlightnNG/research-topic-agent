"""Phase 4.1.2: Node chain runner, optional nodes, resume."""

from __future__ import annotations

import pytest

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec, WorkflowDefinition
from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.workflow.node.definition import build_report_demo_workflow, build_report_workflow
from lit_agent_v2.workflow.node.runner import NodeFailed, WorkflowRunner
from lit_agent_v2.workflow.node.state import WorkflowInterrupted


class Kernel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, node: NodeSpec, context: NodeContext) -> NodeResult:
        self.calls.append(node.id)
        return NodeResult({"value": node.id, "inputs": context.inputs})


class Verifier:
    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept

    def verify(self, node: NodeSpec, context: NodeContext, result: NodeResult) -> Verdict:
        return Verdict(self.accept, reasons=[] if self.accept else ["rejected"])


class Store:
    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.outputs: dict[str, dict] = {}
        self.degraded: list[str] = []

    def state(self, run_id: str, node_id: str) -> str | None:
        return self.states.get(node_id)

    def load_output(self, run_id: str, node_id: str) -> dict | None:
        return self.outputs.get(node_id)

    def commit(self, run_id: str, node_id: str, output: dict, verdict: Verdict) -> None:
        self.states[node_id] = "committed"
        self.outputs[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        self.degraded.append(node_id)


class Events:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []

    def emit(self, event_type: str, *, node_id: str | None = None, **payload) -> None:  # noqa: ANN001
        self.events.append((event_type, node_id))


def _chain() -> WorkflowDefinition:
    return WorkflowDefinition(
        "t",
        "1",
        (
            NodeSpec("a", "first", ("tool.a",), inputs=("request",)),
            NodeSpec("b", "second", ("tool.b",), inputs=("a",)),
        ),
    )


def test_chain_runs_and_commits() -> None:
    kernel, store, events = Kernel(), Store(), Events()
    runner = WorkflowRunner(kernel=kernel, verifier=Verifier(), store=store, events=events)
    outputs = runner.run(_chain(), run_id="r1", inputs={"request": {}})
    assert kernel.calls == ["a", "b"]
    assert outputs["b"]["value"] == "b"
    assert store.states == {"a": "committed", "b": "committed"}
    assert ("node.committed", "b") in events.events


def test_disabled_node_is_skipped() -> None:
    kernel, store = Kernel(), Store()
    workflow = WorkflowDefinition(
        "t", "1", (NodeSpec("a", "first", ("tool.a",), enabled=False),)
    )
    WorkflowRunner(kernel=kernel, verifier=Verifier(), store=store).run(
        workflow, run_id="r1"
    )
    assert kernel.calls == []


def test_required_failure_raises_and_optional_degrades() -> None:
    kernel, store = Kernel(), Store()
    workflow = WorkflowDefinition("t", "1", (NodeSpec("a", "first", ("tool.a",)),))
    with pytest.raises(NodeFailed):
        WorkflowRunner(kernel=kernel, verifier=Verifier(accept=False), store=store).run(
            workflow, run_id="r1"
        )

    kernel2, store2 = Kernel(), Store()
    optional = WorkflowDefinition(
        "t", "1", (NodeSpec("a", "first", ("tool.a",), optional=True),)
    )
    outputs = WorkflowRunner(
        kernel=kernel2, verifier=Verifier(accept=False), store=store2
    ).run(optional, run_id="r1")
    assert outputs["a"]["degraded"] is True
    assert store2.degraded == ["a"]


def test_resume_uses_committed_output() -> None:
    kernel, store = Kernel(), Store()
    store.states["a"] = "committed"
    store.outputs["a"] = {"value": "saved"}
    runner = WorkflowRunner(kernel=kernel, verifier=Verifier(), store=store)
    outputs = runner.run(_chain(), run_id="r1", inputs={"request": {}}, resume=True)
    assert outputs["a"] == {"value": "saved"}
    assert kernel.calls == ["b"]


def test_pause_at_node_boundary() -> None:
    kernel, store = Kernel(), Store()
    runner = WorkflowRunner(
        kernel=kernel,
        verifier=Verifier(),
        store=store,
        control=lambda: "paused",
    )
    with pytest.raises(WorkflowInterrupted):
        runner.run(_chain(), run_id="r1")


def test_report_workflow_disables_classification() -> None:
    demo = build_report_workflow(FeatureProfile(classification=False))
    ids = [node.id for node in demo.nodes]
    assert "map.classify" not in ids
    assert ids == ["source.collect", "evidence.extract", "report.generate", "finalize"]

    full = build_report_workflow(FeatureProfile(classification=True))
    assert "map.classify" in [node.id for node in full.nodes]


def test_report_workflow_validation() -> None:
    workflow = build_report_workflow(FeatureProfile(classification=False))
    assert workflow.validate() == []


def test_report_demo_workflow_shape() -> None:
    workflow = build_report_demo_workflow()
    assert workflow.validate() == []
    assert [node.id for node in workflow.nodes] == ["report.generate"]
    node = workflow.nodes[0]
    assert "report.write_section" in node.tools
    assert "report.persist" in node.tools
    assert node.max_tokens == 12000
