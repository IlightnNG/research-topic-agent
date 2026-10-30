"""Workflow artifact and checkpoint stores (Phase 3.4 / S6)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["ArtifactStore", "CheckpointStore", "WorkflowCheckpoint"]


class ArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        self._items[key] = value

    def get(self, key: str) -> Any:
        return self._items.get(key)

    def require(self, key: str) -> Any:
        if key not in self._items:
            raise KeyError(key)
        return self._items[key]

    def snapshot(self) -> dict[str, Any]:
        return dict(self._items)


@dataclass
class WorkflowCheckpoint:
    workflow: str
    completed: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    failed_node: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "completed": self.completed,
            "artifacts": self.artifacts,
            "failed_node": self.failed_node,
            "error": self.error,
        }


class CheckpointStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._state: WorkflowCheckpoint | None = None

    def save(self, state: WorkflowCheckpoint) -> None:
        self._state = state
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state.to_dict(), ensure_ascii=False), encoding="utf-8")

    def load(self) -> WorkflowCheckpoint | None:
        if self._state is not None:
            return self._state
        if self.path is not None and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return WorkflowCheckpoint(**data)
        return None
