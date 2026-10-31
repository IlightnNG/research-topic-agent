"""V2 contracts. No imports from the legacy package."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

__all__ = [
    "Event",
    "NodeResult",
    "NodeSpec",
    "NodeState",
    "RunInterrupted",
    "RunRequest",
    "RunState",
    "WorkflowDefinition",
]


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class RunInterrupted(RuntimeError):
    """Raised at a node boundary when pause/abort is requested."""


class NodeState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMMITTED = "committed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class RunRequest:
    topic_id: str
    limit: int = 100
    focus_hint: str | None = None
    workflow: str = "report"


@dataclass(frozen=True)
class NodeSpec:
    id: str
    kind: Literal["agent", "deterministic"]
    input_keys: tuple[str, ...] = ()
    output_key: str = ""
    allowed_tools: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    budget_usd: float = 0.05
    timeout_s: float = 300.0
    verifier: str | None = None


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: str
    nodes: tuple[NodeSpec, ...]


@dataclass
class NodeResult:
    node_id: str
    state: NodeState
    output: dict[str, Any] = field(default_factory=dict)
    artifact_sha: str | None = None
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Event:
    event_id: str
    run_id: str
    seq: int
    type: str
    node_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = ""
