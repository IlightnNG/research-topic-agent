"""Node / workflow contracts for the Node Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.verdict import VerifierProfile

__all__ = [
    "NodeContext",
    "NodeResult",
    "NodeSpec",
    "NodeState",
    "WorkflowDefinition",
]


class NodeState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMMITTED = "committed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class NodeSpec:
    id: str
    goal: str
    tools: tuple[str, ...]
    inputs: tuple[str, ...] = ()
    output_schema: dict[str, Any] | str = ""
    verifier: VerifierProfile = field(default_factory=VerifierProfile)
    max_steps: int = 8
    max_usd: float = 0.20
    max_tokens: int = 4000
    timeout_s: float = 600.0
    optional: bool = False
    enabled: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.id:
            problems.append("node id is required")
        if not self.goal.strip():
            problems.append(f"{self.id}: goal is required")
        if not self.tools:
            problems.append(f"{self.id}: at least one tool is required")
        if self.max_steps < 1:
            problems.append(f"{self.id}: max_steps must be >= 1")
        if self.max_usd < 0:
            problems.append(f"{self.id}: max_usd must be >= 0")
        if self.max_tokens < 1:
            problems.append(f"{self.id}: max_tokens must be >= 1")
        return problems


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: str
    nodes: tuple[NodeSpec, ...]
    features: FeatureProfile = field(default_factory=FeatureProfile)

    def validate(self) -> list[str]:
        problems: list[str] = []
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            problems.append("duplicate node ids")
        for node in self.nodes:
            problems.extend(node.validate())
        outputs: set[str] = set()
        for node in self.nodes:
            for input_key in node.inputs:
                if input_key not in outputs and input_key not in {"request", "features", "requirements"}:
                    problems.append(f"{node.id}: missing input {input_key}")
            outputs.add(node.id)
        return problems


@dataclass
class NodeContext:
    run_id: str
    node_id: str
    goal: str
    features: FeatureProfile
    inputs: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | str = ""


@dataclass
class NodeResult:
    output: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    stop_reason: str = "final"
    checkpoint: dict[str, Any] = field(default_factory=dict)
