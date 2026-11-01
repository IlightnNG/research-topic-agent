"""Run-level state for the Node workflow."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RunState", "WorkflowInterrupted"]


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"
    ABORTED = "aborted"


class WorkflowInterrupted(RuntimeError):
    def __init__(self, state: str) -> None:
        super().__init__(f"workflow interrupted: {state}")
        self.state = state
