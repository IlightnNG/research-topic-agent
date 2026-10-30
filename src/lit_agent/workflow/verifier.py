"""Node acceptance for fixed workflows (Phase 3.4 / S6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent.workflow.spec import NodeSpec

__all__ = ["CodeVerifier", "Verdict", "VerifierAgent"]


@dataclass
class Verdict:
    accept: bool
    reasons: list[str] = field(default_factory=list)
    repair: bool = False

    @property
    def failed_checks(self) -> list[str]:
        return list(self.reasons)


class VerifierAgent(Protocol):
    def verify(self, node: NodeSpec, artifact: Any, artifacts: Any) -> Verdict: ...


class CodeVerifier:
    """Cheap structural checks before any independent agent review."""

    def verify(self, node: NodeSpec, artifact: Any, artifacts: Any) -> Verdict:
        reasons: list[str] = []
        if node.output_key and artifact is None:
            reasons.append("missing output artifact")
        if node.postconditions and not isinstance(artifact, dict):
            reasons.append("artifact must be an object for postconditions")
        elif isinstance(artifact, dict):
            for key in node.postconditions:
                if key not in artifact:
                    reasons.append(f"missing postcondition: {key}")
        return Verdict(accept=not reasons, reasons=reasons, repair=bool(reasons))
