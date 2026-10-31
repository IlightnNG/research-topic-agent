"""V2 node verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.contracts import NodeSpec

__all__ = ["CodeVerifier", "Verdict"]


@dataclass
class Verdict:
    accept: bool
    reasons: list[str] = field(default_factory=list)


class CodeVerifier:
    def verify(self, node: NodeSpec, artifact: dict[str, Any]) -> Verdict:
        missing = [key for key in node.postconditions if key not in artifact]
        if missing:
            return Verdict(False, [f"missing: {key}" for key in missing])
        return Verdict(True)
