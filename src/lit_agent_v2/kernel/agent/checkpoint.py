"""Checkpoint persistence for the generic AgentKernel."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["KernelCheckpoint", "FileCheckpointStore"]


@dataclass
class KernelCheckpoint:
    task_id: str
    step: int
    state: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    stop_reason: str = "running"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> KernelCheckpoint:
        return cls(
            task_id=str(payload.get("task_id") or ""),
            step=int(payload.get("step") or 0),
            state=dict(payload.get("state") or {}),
            usage=dict(payload.get("usage") or {}),
            cost_usd=float(payload.get("cost_usd") or 0.0),
            stop_reason=str(payload.get("stop_reason") or "running"),
        )


class FileCheckpointStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in task_id)
        return self.root / f"{safe}.json"

    def save(self, checkpoint: KernelCheckpoint) -> Path:
        path = self._path(checkpoint.task_id)
        path.write_text(
            json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, task_id: str) -> KernelCheckpoint | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        return KernelCheckpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def clear(self, task_id: str) -> None:
        path = self._path(task_id)
        if path.exists():
            path.unlink()
