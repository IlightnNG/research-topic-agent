"""Code + audit verification contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AuditResult",
    "CodeCheck",
    "Verdict",
    "VerifierProfile",
    "make_verdict",
]


@dataclass(frozen=True)
class VerifierProfile:
    code: tuple[str, ...] = ("schema",)
    audit: str | None = "default"
    audit_required: bool = True


@dataclass(frozen=True)
class CodeCheck:
    check_id: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "reason": self.reason}


@dataclass
class AuditResult:
    scores: dict[str, float] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    verdict: str = "repair"
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": self.scores,
            "problems": self.problems,
            "verdict": self.verdict,
            "accepted": self.accepted,
        }


@dataclass
class Verdict:
    accept: bool
    code: list[CodeCheck] = field(default_factory=list)
    audit: AuditResult = field(default_factory=AuditResult)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accept": self.accept,
            "code": [check.to_dict() for check in self.code],
            "audit": self.audit.to_dict(),
            "reasons": self.reasons,
        }


def make_verdict(code: list[CodeCheck], audit: AuditResult, *, audit_required: bool = True) -> Verdict:
    code_ok = all(check.passed for check in code) if code else True
    audit_ok = audit.accepted or not audit_required
    reasons = [check.reason for check in code if not check.passed]
    reasons.extend(audit.problems)
    return Verdict(
        accept=code_ok and audit_ok,
        code=code,
        audit=audit,
        reasons=reasons,
    )
