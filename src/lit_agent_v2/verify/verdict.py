"""Combined code + audit verifier."""

from __future__ import annotations

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.contracts.verdict import AuditResult, Verdict, make_verdict
from lit_agent_v2.verify.audit import AuditVerifier
from lit_agent_v2.verify.code import CodeVerifier

__all__ = ["Verifier"]


class Verifier:
    def __init__(
        self,
        *,
        code: CodeVerifier | None = None,
        audit: AuditVerifier | None = None,
    ) -> None:
        self.code = code or CodeVerifier()
        self.audit = audit

    def verify(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> Verdict:
        checks = self.code.verify(node, context, result)
        audit_required = node.verifier.audit is not None and node.verifier.audit_required
        if node.verifier.audit is None:
            audit = AuditResult(accepted=True, verdict="skipped")
        elif self.audit is None:
            audit = AuditResult(
                accepted=False,
                verdict="repair",
                problems=["audit_unavailable"],
            )
        else:
            audit = self.audit.audit(node, context, result)
        return make_verdict(checks, audit, audit_required=audit_required)
