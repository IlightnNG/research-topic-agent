"""Report planning and assembly tools; section writing is added by report node."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.contracts.artifacts import PlanSection, ReportPlan
from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.tool import ToolSpec

__all__ = ["assemble_report", "build_report_tools", "check_section", "plan_report"]


def plan_report(
    papers: list[dict[str, Any]],
    *,
    features: FeatureProfile | None = None,
    requirements: ReportRequirements | None = None,
    chunk_size: int = 5,
) -> dict[str, Any]:
    features = features or FeatureProfile()
    requirements = requirements or ReportRequirements()
    section_kinds = set(features.enabled_sections())
    sections: list[PlanSection] = []
    if "overview" in section_kinds:
        sections.append(PlanSection("overview", "overview", "At a Glance", 180))
    if "paper_analysis" in section_kinds:
        for start in range(0, len(papers), chunk_size):
            chunk = papers[start : start + chunk_size]
            ids = tuple(str(paper.get("paper_id")) for paper in chunk)
            sections.append(
                PlanSection(
                    f"paper_analysis_{start // chunk_size + 1:03d}",
                    "paper_analysis",
                    f"Papers {start + 1}-{start + len(chunk)}",
                    220,
                    ids,
                )
            )
    if "synthesis" in section_kinds:
        sections.append(PlanSection("synthesis", "synthesis", "Cross-Paper Synthesis", 250))
    sections.append(PlanSection("paper_index", "paper_index", "Paper Index", 0))
    plan = ReportPlan("Report", sections)
    problems = plan.validate(requirements)
    if problems:
        raise ValueError("; ".join(problems))
    return plan.to_dict()


def check_section(section: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    body = str(section.get("body") or "")
    known = {str(claim.get("claim_id")) for claim in claims}
    refs = set()
    for token in body.replace("[", " ").replace("]", " ").split():
        if token.startswith("C") and token[1:].isdigit():
            refs.add(token)
    problems = []
    if not body.strip():
        problems.append("empty section")
    if not refs:
        problems.append("no claim citations")
    if known and not refs:
        problems.append("unknown claim refs")
    return {"ok": not problems, "problems": problems, "refs": sorted(refs)}


def assemble_report(
    title: str, sections: list[dict[str, Any]], *, state: str = "complete"
) -> dict[str, Any]:
    body = "\n\n".join(str(section.get("body") or "") for section in sections)
    return {
        "title": title,
        "content_md": body,
        "sections": sections,
        "word_count": len(body.split()),
        "state": state,
    }


def build_report_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            "report.plan",
            "Build a section plan from papers, features, and requirements.",
            {
                "type": "object",
                "properties": {
                    "papers": {"type": "array", "items": {"type": "object"}},
                    "chunk_size": {"type": "integer"},
                },
                "required": ["papers"],
            },
            {"type": "object"},
            handler=lambda args: plan_report(
                args["papers"], chunk_size=int(args.get("chunk_size", 5))
            ),
        ),
        ToolSpec(
            "report.check_section",
            "Check a section for citations and empty body.",
            {
                "type": "object",
                "properties": {
                    "section": {"type": "object"},
                    "claims": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["section", "claims"],
            },
            {"type": "object"},
            handler=lambda args: check_section(args["section"], args["claims"]),
        ),
        ToolSpec(
            "report.assemble",
            "Assemble section artifacts into a report draft.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sections": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["title", "sections"],
            },
            {"type": "object"},
            handler=lambda args: assemble_report(args["title"], args["sections"]),
        ),
    ]
