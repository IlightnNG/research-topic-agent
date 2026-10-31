"""Kernel step checkpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["KernelCheckpoint", "KernelCheckpointStore"]


@dataclass
class KernelCheckpoint:
    node_id: str
    step: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "node_id": self.node_id,
            "step": self.step,
            "history": self.history,
            "trace": self.trace,
            "cost_usd": self.cost_usd,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "stop_reason": self.stop_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KernelCheckpoint:
        return cls(
            node_id=str(data.get("node_id") or ""),
            step=int(data.get("step") or 0),
            history=list(data.get("history") or []),
            trace=list(data.get("trace") or []),
            cost_usd=float(data.get("cost_usd") or 0.0),
            prompt_tokens=int(data.get("prompt_tokens") or 0),
            completion_tokens=int(data.get("completion_tokens") or 0),
            stop_reason=data.get("stop_reason"),
        )


class KernelCheckpointStore:
    """Persist a kernel step checkpoint into run_nodes.checkpoint_json."""

    def __init__(self, db, run_id: str) -> None:
        self.db = db
        self.run_id = run_id

    def save(self, checkpoint: KernelCheckpoint) -> None:
        import json

        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO run_nodes(run_id,node_id,state,attempt,checkpoint_json)"
                " VALUES (?,?,?,?,?) ON CONFLICT(run_id,node_id) DO UPDATE SET"
                " checkpoint_json=excluded.checkpoint_json",
                (
                    self.run_id,
                    checkpoint.node_id,
                    "running",
                    1,
                    json.dumps(checkpoint.to_dict(), ensure_ascii=False),
                ),
            )

    def load(self, node_id: str) -> KernelCheckpoint | None:
        import json

        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT checkpoint_json FROM run_nodes WHERE run_id=? AND node_id=?",
                (self.run_id, node_id),
            ).fetchone()
        if row is None or not row[0]:
            return None
        return KernelCheckpoint.from_dict(json.loads(row[0]))
