"""Report-level citation, duplicate and word audit."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lit_agent_v2.contracts.report import ReportDraft

__all__ = ["ReportAudit", "audit_report"]

_CITATION = re.compile(r"\[C(\d+)\]")
_APPENDIX = {"paper_index", "claim_ledger"}


@dataclass(frozen=True)
class ReportAudit:
    narrative_words: int
    cited_claims: int
    total_claims: int
    uncited_facts: int
    duplicate_claim_rate: float
    citation_coverage: float


def audit_report(draft: ReportDraft) -> ReportAudit:
    narrative = "\n\n".join(
        section.body for section in draft.sections if section.kind not in _APPENDIX
    )
    claim_ids = [str(claim.get("claim_id")) for claim in draft.claims]
    cited: set[str] = set()
    seen_refs: set[str] = set()
    duplicate_occurrences = 0
    for section in draft.sections:
        if section.kind != "deep_dive":
            continue
        for line in section.body.splitlines():
            if not line.strip().startswith("- "):
                continue
            ids = _CITATION.findall(line)
            for raw in ids:
                index = int(raw) - 1
                if 0 <= index < len(claim_ids):
                    cited.add(claim_ids[index])
                if raw in seen_refs:
                    duplicate_occurrences += 1
                else:
                    seen_refs.add(raw)
    deep_citations = sum(
        1
        for section in draft.sections
        if section.kind == "deep_dive"
        for _ in _CITATION.finditer(section.body)
    )
    uncited = sum(
        1
        for section in draft.sections
        if section.kind == "deep_dive"
        for line in section.body.splitlines()
        if line.strip().startswith("- ")
        and re.search(r"[A-Za-z]", line)
        and not _CITATION.search(line)
    )
    total = max(1, len(draft.claims))
    return ReportAudit(
        narrative_words=len(re.findall(r"\S+", narrative)),
        cited_claims=len(cited),
        total_claims=len(draft.claims),
        uncited_facts=uncited,
        duplicate_claim_rate=duplicate_occurrences / max(1, deep_citations),
        citation_coverage=len(cited) / total,
    )
