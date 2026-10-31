"""M4-P02 plan and evidence pack contracts (internal to M4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.contracts.report import EvidenceArtifact, MapArtifact
from lit_agent_v2.domains.report.policy import ReportPolicy

__all__ = ["EvidencePack", "PlanSection", "ReportPlan", "build_plan", "pack_for"]


@dataclass
class PlanSection:
    section_id: str
    kind: str
    title: str
    target_words: int
    paper_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)


@dataclass
class ReportPlan:
    title: str
    sections: list[PlanSection]
    policy: ReportPolicy


@dataclass
class EvidencePack:
    direction_id: str
    name: str
    target_words: int
    papers: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    claim_refs: dict[str, str]


def build_plan(
    *, title: str, evidence: EvidenceArtifact, mapping: MapArtifact, policy: ReportPolicy
) -> ReportPlan:
    direction_budget = max(140, int(policy.target_words * 0.55 / max(1, len(mapping.directions))))
    sections = [
        PlanSection("overview", "overview", "At a Glance", 180),
    ]
    for direction in mapping.directions:
        sections.append(
            PlanSection(
                direction.direction_id,
                "deep_dive",
                direction.name,
                direction_budget,
                paper_ids=list(direction.paper_ids),
                claim_ids=list(direction.claim_ids),
            )
        )
    sections.extend(
        [
            PlanSection("comparison", "comparison", "Comparison Matrix", 220),
            PlanSection("gaps", "gaps", "Gaps & Limitations", 160),
            PlanSection("method", "method", "Method & Scope", 130),
            PlanSection("index", "paper_index", "Paper Index", 0),
            PlanSection("ledger", "claim_ledger", "Claim Ledger", 0),
        ]
    )
    return ReportPlan(title=title, sections=sections, policy=policy)


def pack_for(
    plan: ReportPlan, direction_id: str, evidence: EvidenceArtifact, mapping: MapArtifact
) -> EvidencePack | None:
    direction = next((item for item in mapping.directions if item.direction_id == direction_id), None)
    if direction is None:
        return None
    by_paper = {paper["paper_id"]: paper for paper in evidence.papers}
    claims = [claim for paper in evidence.papers for claim in paper.get("claims", [])]
    refs = {str(claim["claim_id"]): f"C{index + 1}" for index, claim in enumerate(claims)}
    direction_claims = [
        {**claim, "ref": refs[str(claim["claim_id"])]}
        for claim in claims
        if str(claim["claim_id"]) in set(direction.claim_ids)
    ]
    papers = [
        {
            "paper_id": pid,
            "title": by_paper.get(pid, {}).get("title", ""),
            "authors": by_paper.get(pid, {}).get("authors", []),
            "venue": by_paper.get(pid, {}).get("venue", ""),
            "year": by_paper.get(pid, {}).get("year"),
        }
        for pid in direction.paper_ids
    ]
    section = next(item for item in plan.sections if item.section_id == direction_id)
    return EvidencePack(
        direction_id=direction_id,
        name=direction.name,
        target_words=section.target_words,
        papers=papers,
        claims=direction_claims,
        claim_refs=refs,
    )
