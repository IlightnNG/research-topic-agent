"""Ports used by the Node workflow runner."""

from __future__ import annotations

from typing import Any, Protocol

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.contracts.tool import ToolResult
from lit_agent_v2.contracts.verdict import Verdict

__all__ = ["EventPort", "KernelPort", "NodeStorePort", "VerifierPort"]


class KernelPort(Protocol):
    def run(self, node: NodeSpec, context: NodeContext) -> NodeResult: ...


class VerifierPort(Protocol):
    def verify(self, node: NodeSpec, context: NodeContext, result: NodeResult) -> Verdict: ...


class NodeStorePort(Protocol):
    def state(self, run_id: str, node_id: str) -> str | None: ...
    def load_output(self, run_id: str, node_id: str) -> dict[str, Any] | None: ...
    def commit(
        self,
        run_id: str,
        node_id: str,
        output: dict[str, Any],
        verdict: Verdict,
    ) -> None: ...
    def degrade(self, run_id: str, node_id: str, reason: str) -> None: ...


class EventPort(Protocol):
    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> None: ...


class ToolRegistryPort(Protocol):
    def call(self, name: str, args: dict[str, Any]) -> ToolResult: ...
