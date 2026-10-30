"""Layered kernel context (Phase 3.4 / S3 baseline)."""

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

    def handoff(self, *, max_chars: int = 4000) -> Handoff:
        summary = json.dumps(self.working, ensure_ascii=False, default=str)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."
        return Handoff(
            invariants=dict(self.invariants),
            artifacts=dict(self.artifacts),
            working_summary=summary,
            raw_refs=self.raw_refs[-20:],
        )

    def reset_node(self) -> None:
        self.working.clear()
        self.raw_refs.clear()


@dataclass
class Handoff:
    invariants: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    working_summary: str = ""
    raw_refs: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        return json.dumps(
            {
                "invariants": self.invariants,
                "artifacts": self.artifacts,
                "working_summary": self.working_summary,
                "raw_refs": self.raw_refs,
            },
            ensure_ascii=False,
            default=str,
        )
