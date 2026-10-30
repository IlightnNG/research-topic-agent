"""Node acceptance for fixed workflows (Phase 3.4 / S6-S7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent.workflow.spec import NodeSpec

__all__ = ["AgentVerifier", "CodeVerifier", "Verdict", "VerifierAgent"]


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


class AgentVerifier:
    """Independent verifier: fresh prompt, artifact only, no producer trace."""

    def __init__(self, gateway: Any, *, max_tokens: int = 400) -> None:
        self.gateway = gateway
        self.max_tokens = max_tokens

    def verify(self, node: NodeSpec, artifact: Any, artifacts: Any) -> Verdict:
        try:
            payload, _ = self.gateway.chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are an independent verifier. Do not rewrite the artifact. "
                            'Return JSON only: {"verdict":"accept|repair|fail",'
                            '"reasons":[str]}. Reject missing citations, '
                            "unsupported claims, or contract violations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Node: {node.id}\nGoal: {node.goal}\n"
                            f"Contract: output={node.output_key}, "
                            f"postconditions={list(node.postconditions)}\n"
                            f"Artifact: {artifact!r}"
                        ),
                    },
                ],
                max_tokens=self.max_tokens,
                agent="verifier",
            )
            if not isinstance(payload, dict):
                return Verdict(accept=False, reasons=["verifier returned non-object"])
            raw = str(payload.get("verdict") or "fail")
            reasons = [str(item) for item in (payload.get("reasons") or [])]
            if raw == "accept":
                return Verdict(accept=True, reasons=reasons)
            return Verdict(accept=False, reasons=reasons or [raw], repair=raw == "repair")
        except Exception as exc:  # noqa: BLE001 - verifier failure is a rejection, not a crash
            return Verdict(accept=False, reasons=[f"verifier error: {type(exc).__name__}"])
