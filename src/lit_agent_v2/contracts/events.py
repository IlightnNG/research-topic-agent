"""Shared event envelope contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["EventEnvelope"]


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    run_id: str
    seq: int
    ts: str
    type: str
    module: str
    node_id: str | None = None
    severity: str = "info"
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "run_id": self.run_id,
            "seq": self.seq,
            "ts": self.ts,
            "type": self.type,
            "module": self.module,
            "node_id": self.node_id,
            "severity": self.severity,
            "payload": self.payload,
        }
