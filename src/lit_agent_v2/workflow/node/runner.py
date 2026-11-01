"""Generic Node chain runner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lit_agent_v2.contracts.node import NodeContext, NodeState, WorkflowDefinition
from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.workflow.node.ports import EventPort, KernelPort, NodeStorePort, VerifierPort
from lit_agent_v2.workflow.node.state import WorkflowInterrupted

__all__ = ["NodeFailed", "WorkflowRunner"]

_RUN_INPUTS = {"request", "features", "requirements"}


class NodeFailed(RuntimeError):
    def __init__(self, node_id: str, verdict: Verdict) -> None:
        super().__init__(f"node failed: {node_id}")
        self.node_id = node_id
        self.verdict = verdict


class WorkflowRunner:
    def __init__(
        self,
        *,
        kernel: KernelPort,
        verifier: VerifierPort,
        store: NodeStorePort,
        events: EventPort | None = None,
        control: Callable[[], str] | None = None,
    ) -> None:
        self.kernel = kernel
        self.verifier = verifier
        self.store = store
        self.events = events
        self.control = control

    def run(
        self,
        definition: WorkflowDefinition,
        *,
        run_id: str,
        inputs: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        outputs: dict[str, Any] = dict(inputs or {})
        for node in definition.nodes:
            if self.control is not None and self.control() != "running":
                raise WorkflowInterrupted(self.control())
            if not node.enabled:
                self._emit("node.skipped", node.id, reason="disabled")
                continue
            if resume and self.store.state(run_id, node.id) == NodeState.COMMITTED:
                loaded = self.store.load_output(run_id, node.id)
                if loaded is not None:
                    outputs[node.id] = loaded
                    self._emit("node.committed", node.id, resumed=True)
                    continue
            missing = [key for key in node.inputs if key not in outputs and key not in _RUN_INPUTS]
            if missing:
                raise NodeFailed(
                    node.id,
                    Verdict(False, reasons=[f"missing inputs: {missing}"]),
                )
            context = NodeContext(
                run_id=run_id,
                node_id=node.id,
                goal=node.goal,
                features=definition.features,
                inputs={key: outputs[key] for key in node.inputs if key in outputs},
                output_schema=node.output_schema,
            )
            self._emit("node.started", node.id)
            result = self.kernel.run(node, context)
            if result.stop_reason == "cancelled":
                raise WorkflowInterrupted("paused")
            self._emit("node.verifying", node.id)
            verdict = self.verifier.verify(node, context, result)
            if verdict.accept:
                self.store.commit(run_id, node.id, result.output, verdict)
                outputs[node.id] = result.output
                self._emit("node.committed", node.id)
                continue
            if node.optional:
                self.store.degrade(run_id, node.id, "; ".join(verdict.reasons))
                outputs[node.id] = {"degraded": True, "reasons": verdict.reasons}
                self._emit("node.degraded", node.id, reasons=verdict.reasons)
                continue
            self._emit("node.failed", node.id, reasons=verdict.reasons)
            raise NodeFailed(node.id, verdict)
        return outputs

    def _emit(self, event_type: str, node_id: str, **payload: Any) -> None:
        if self.events is not None:
            self.events.emit(event_type, node_id=node_id, **payload)
