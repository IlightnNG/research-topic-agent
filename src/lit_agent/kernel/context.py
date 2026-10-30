"""Layered kernel context (Phase 3.4 / S4).

L0 invariants survive nodes; L1 artifact summaries are referenced; L2 is
node-local; L3 raw tool output is represented by refs only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ContextLayers", "Handoff"]


@dataclass
class ContextLayers:
    invariants: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    working: dict[str, Any] = field(default_factory=dict)
    raw_refs: list[str] = field(default_factory=list)
    node_id: str | None = None

    def start_node(self, node_id: str) -> None:
        """Enter a node: keep L0/L1, drop L2/L3 from the previous node."""
        self.node_id = node_id
        self.working.clear()
        self.raw_refs.clear()
        self.working["node_id"] = node_id

    def finish_node(self, artifact_key: str, summary: str) -> Handoff:
        """Leave a node: publish an artifact reference and compress working state."""
        self.artifacts[artifact_key] = summary
        handoff = self.handoff()
        self.working.clear()
        self.raw_refs.clear()
        self.node_id = None
        return handoff

    def compress(self, *, max_chars: int = 2000) -> str:
        raw = json.dumps(self.working, ensure_ascii=False, default=str)
        if len(raw) <= max_chars:
            return raw
        compact = {"node_id": self.node_id, "keys": sorted(self.working), "truncated": True}
        return json.dumps(compact, ensure_ascii=False)[:max_chars]

    def handoff(self, *, max_chars: int = 4000) -> Handoff:
        summary = json.dumps(self.working, ensure_ascii=False, default=str)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."
        return Handoff(
            invariants=dict(self.invariants),
            artifacts=dict(self.artifacts),
            working_summary=summary,
            raw_refs=self.raw_refs[-20:],
            node_id=self.node_id,
        )

    def reset_node(self) -> None:
        self.working.clear()
        self.raw_refs.clear()
        self.node_id = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariants": self.invariants,
            "artifacts": self.artifacts,
            "working": self.working,
            "raw_refs": self.raw_refs,
            "node_id": self.node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextLayers:
        return cls(
            invariants=dict(data.get("invariants") or {}),
            artifacts=dict(data.get("artifacts") or {}),
            working=dict(data.get("working") or {}),
            raw_refs=list(data.get("raw_refs") or []),
            node_id=data.get("node_id"),
        )


@dataclass
class Handoff:
    invariants: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    working_summary: str = ""
    raw_refs: list[str] = field(default_factory=list)
    node_id: str | None = None

    def to_prompt(self) -> str:
        return json.dumps(
            {
                "invariants": self.invariants,
                "artifacts": self.artifacts,
                "working_summary": self.working_summary,
                "raw_refs": self.raw_refs,
                "node_id": self.node_id,
            },
            ensure_ascii=False,
            default=str,
        )
