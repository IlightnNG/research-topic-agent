"""Report node verifier (Phase 3.5 / S7)."""

from __future__ import annotations

from typing import Any

from lit_agent.workflow.spec import NodeSpec
from lit_agent.workflow.verifier import AgentVerifier, Verdict

__all__ = ["ReportVerifier"]


class ReportVerifier:
    """Cheap node-specific gate, plus optional independent LLM review."""

    def __init__(self, agent: AgentVerifier | None = None) -> None:
        self.agent = agent

    def verify(self, node: NodeSpec, artifact: Any, artifacts: Any) -> Verdict:
        if not isinstance(artifact, dict):
            return Verdict(accept=False, reasons=["artifact is not an object"])
        if node.id == "source" and int(artifact.get("count") or 0) <= 0:
            return Verdict(accept=False, reasons=["source returned no papers"])
        if node.id == "evidence" and not artifact.get("context_id"):
            return Verdict(accept=False, reasons=["missing evidence context"])
        if node.id == "map" and int(artifact.get("directions") or 0) <= 0:
            return Verdict(accept=False, reasons=["no directions"])
        if node.id == "write" and not artifact.get("report_id"):
            return Verdict(accept=False, reasons=["report id missing"])
        if self.agent is not None and node.id == "write":
            return self.agent.verify(node, artifact, artifacts)
        return Verdict(accept=True)
