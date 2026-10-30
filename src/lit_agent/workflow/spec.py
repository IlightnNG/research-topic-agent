"""Fixed workflow declarations (Phase 3.4 / S1).

The workflow is intentionally static: there is no runtime planning here.
Kernel-local planning belongs to the kernel, not this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = ["NodeKind", "NodeSpec", "WorkflowSpec", "validate_workflow"]

NodeKind = Literal["deterministic", "agent"]


@dataclass(frozen=True)
class NodeSpec:
    id: str
    kind: NodeKind
    goal: str
    input_keys: tuple[str, ...] = ()
    output_key: str = ""
    allowed_tools: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    budget_usd: float = 0.0
    timeout_s: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "goal": self.goal,
            "input_keys": list(self.input_keys),
            "output_key": self.output_key,
            "allowed_tools": list(self.allowed_tools),
            "postconditions": list(self.postconditions),
            "budget_usd": self.budget_usd,
            "timeout_s": self.timeout_s,
        }


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    nodes: tuple[NodeSpec, ...] = field(default_factory=tuple)

    def node(self, node_id: str) -> NodeSpec:
        for item in self.nodes:
            if item.id == node_id:
                return item
        raise KeyError(node_id)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "nodes": [node.to_dict() for node in self.nodes]}


def validate_workflow(spec: WorkflowSpec) -> list[str]:
    """Return schema errors. Execution order is declaration order."""
    problems: list[str] = []
    seen: set[str] = set()
    produced: set[str] = set()
    for node in spec.nodes:
        if not node.id:
            problems.append("node id is empty")
        if node.id in seen:
            problems.append(f"duplicate node id: {node.id}")
        seen.add(node.id)
        if node.kind not in {"deterministic", "agent"}:
            problems.append(f"{node.id}: invalid kind")
        if node.kind == "deterministic" and not node.output_key:
            problems.append(f"{node.id}: deterministic node needs output_key")
        if node.kind == "agent" and not node.allowed_tools:
            problems.append(f"{node.id}: agent node needs allowed_tools")
        for key in node.input_keys:
            if key not in produced:
                problems.append(f"{node.id}: input not produced earlier: {key}")
        if node.output_key:
            produced.add(node.output_key)
    return problems
