"""Fixed workflow runner (Phase 3.4 / S6). No runtime planning."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lit_agent.kernel.events import EventSink, emit
from lit_agent.kernel.runtime import Kernel
from lit_agent.kernel.types import KernelGoal
from lit_agent.workflow.artifacts import ArtifactStore, CheckpointStore, WorkflowCheckpoint
from lit_agent.workflow.spec import NodeSpec, WorkflowSpec
from lit_agent.workflow.verifier import CodeVerifier, VerifierAgent

__all__ = ["WorkflowResult", "WorkflowRunner"]

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    name: str
    completed: list[str]
    artifacts: dict[str, Any]
    failed_node: str | None = None
    error: str | None = None


class WorkflowRunner:
    def __init__(
        self,
        spec: WorkflowSpec,
        *,
        kernel: Kernel,
        handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        completers: dict[str, Callable[..., dict[str, Any]]] | None = None,
        verifier: VerifierAgent | None = None,
        checkpoint: CheckpointStore | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.spec = spec
        self.kernel = kernel
        self.handlers = handlers or {}
        self.completers = completers or {}
        self.code_verifier = CodeVerifier()
        self.verifier = verifier
        self.checkpoint = checkpoint or CheckpointStore()
        self.event_sink = event_sink
        self.artifacts = ArtifactStore()

    def run(self, inputs: dict[str, Any] | None = None, *, resume: bool = True) -> WorkflowResult:
        for key, value in (inputs or {}).items():
            self.artifacts.put(key, value)
        saved = self.checkpoint.load() if resume else None
        completed = list(saved.completed) if saved else []
        if saved:
            for key, value in saved.artifacts.items():
                self.artifacts.put(key, value)

        for node in self.spec.nodes:
            if node.id in completed:
                continue
            emit(self.event_sink, "node.started", workflow=self.spec.name, node_id=node.id)
            inputs_payload = {key: self.artifacts.require(key) for key in node.input_keys}
            try:
                artifact, steps = self._execute(node, inputs_payload)
                if node.output_key:
                    self.artifacts.put(node.output_key, artifact)
                verdict = self.code_verifier.verify(node, artifact, self.artifacts)
                if not verdict.accept:
                    raise RuntimeError(f"code gate rejected: {verdict.reasons[:2]}")
                if self.verifier is not None:
                    verdict = self.verifier.verify(node, artifact, self.artifacts)
                    if not verdict.accept:
                        raise RuntimeError(f"verifier rejected: {verdict.reasons[:2]}")
                completed.append(node.id)
                self._save(completed)
                emit(
                    self.event_sink,
                    "node.finished",
                    workflow=self.spec.name,
                    node_id=node.id,
                    steps=steps,
                )
            except Exception as exc:  # noqa: BLE001 - stop at failed node
                logger.warning(
                    "workflow.node_failed",
                    extra={"workflow": self.spec.name, "node": node.id, "error": str(exc)},
                )
                self._save(completed, failed=node.id, error=str(exc))
                emit(
                    self.event_sink,
                    "node.failed",
                    workflow=self.spec.name,
                    node_id=node.id,
                    error=str(exc),
                )
                return WorkflowResult(
                    name=self.spec.name,
                    completed=completed,
                    artifacts=self.artifacts.snapshot(),
                    failed_node=node.id,
                    error=str(exc),
                )

        return WorkflowResult(
            name=self.spec.name,
            completed=completed,
            artifacts=self.artifacts.snapshot(),
        )

    def _execute(self, node: NodeSpec, inputs_payload: dict[str, Any]) -> tuple[Any, int]:
        if node.kind == "deterministic":
            handler = self.handlers.get(node.id)
            if handler is None:
                raise RuntimeError(f"missing deterministic handler: {node.id}")
            return handler(inputs_payload), 0
        result = self.kernel.run(
            KernelGoal(
                node_id=node.id,
                objective=node.goal,
                allowed_tools=node.allowed_tools,
                max_usd=node.budget_usd or 0.05,
                timeout_s=node.timeout_s,
            ),
            completer=self.completers.get(node.id),
        )
        if result.stop_reason != "final":
            raise RuntimeError(f"kernel stopped: {result.stop_reason}")
        return result.output, result.steps_used

    def _save(self, completed: list[str], *, failed: str | None = None, error: str | None = None) -> None:
        self.checkpoint.save(
            WorkflowCheckpoint(
                workflow=self.spec.name,
                completed=list(completed),
                artifacts=self.artifacts.snapshot(),
                failed_node=failed,
                error=error,
            )
        )
