"""Report planning and assembly tools; section writing is added by report node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from lit_agent_v2.contracts.artifacts import PlanSection, ReportPlan
from lit_agent_v2.contracts.features import FeatureProfile, ReportRequirements
from lit_agent_v2.contracts.tool import ToolSpec

__all__ = [
    "assemble_report",
    "build_report_tools",
    "check_section",
    "persist_report",
    "plan_report",
    "write_section",
]


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


REPORT_TEMPLATE = """# <Report title>

## At a Glance
Two to four sentences that summarize the corpus, its main themes, and its scope.

## Papers 1-5
**<paper_id>.** One paragraph for the paper, using only supplied claims. Every factual sentence ends with its [C#] citation.

## Papers 6-10
**<paper_id>.** Same structure as above.

## Cross-Paper Synthesis
Two to three paragraphs: agreements, tensions, and open gaps across papers.

## Paper Index
- <paper_id>: <paper title>
"""


def _claim_keys(claims: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        keys.add(f"C{index}")
        claim_id = str(claim.get("claim_id") or "")
        if claim_id:
            keys.add(claim_id)
    return keys


def check_section(section: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    body = str(section.get("body") or "")
    known = _claim_keys(claims)
    refs = set()
    for token in body.replace("[", " ").replace("]", " ").split():
        if token.startswith("C") and token[1:].isdigit():
            refs.add(token)
    problems = []
    if not body.strip():
        problems.append("empty section")
    if not refs:
        problems.append("no claim citations")
    unknown = refs - known
    if unknown:
        problems.append(f"unknown claim refs: {sorted(unknown)}")
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


class SectionLLMPort(Protocol):
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str = "section-v1",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> tuple[dict, Any]: ...


def write_section(
    section: dict[str, Any],
    claims: list[dict[str, Any]],
    llm: SectionLLMPort,
    *,
    language: str = "en",
) -> dict[str, Any]:
    kind = str(section.get("kind") or "paper_analysis")
    title = str(section.get("title") or kind)
    paper_ids = [str(value) for value in section.get("paper_ids") or []]
    claim_lines = [
        {
            "claim_id": str(claim.get("claim_id")),
            "paper_id": str(claim.get("paper_id")),
            "quote": str(claim.get("quote") or claim.get("text") or ""),
        }
        for claim in claims
        if claim.get("claim_id")
    ]
    rules = {
        "overview": "Write 2-4 sentences summarizing the corpus and its main themes.",
        "paper_analysis": (
            "Write one short paragraph per paper id in this section. "
            "Every factual sentence must cite a claim."
        ),
        "synthesis": "Write cross-paper synthesis: agreements, tensions, and gaps.",
        "paper_index": "Write a compact list mapping paper ids to claim ids.",
    }.get(kind, "Write the requested section using only the supplied claims.")
    prompt = (
        "Write one report section body. Use only the supplied claims.\n"
        "Every factual sentence must cite [C#] where # is the claim index in the supplied list.\n"
        "Do not invent papers, claims, numbers, or citations.\n"
        f"Write the section in {'Chinese' if language == 'zh' else 'English'}.\n"
        "Return JSON only: {\"body\":\"markdown\"}\n"
        "Do not output a section heading; the report renderer adds it.\n"
        "Follow this report-wide format template:\n"
        f"{REPORT_TEMPLATE}\n"
        f"Section kind: {kind}\nTitle: {title}\nPaper ids: {paper_ids}\n"
        f"Rules: {rules}\nClaims: {claim_lines}"
    )
    payload, _usage = llm.chat_json(
        [
            {"role": "system", "content": "You write evidence-grounded report sections."},
            {"role": "user", "content": prompt},
        ],
        prompt_version=f"section-{kind}-v1",
        max_tokens=1800,
        temperature=0.1,
    )
    body = str(payload.get("body") or "") if isinstance(payload, dict) else ""
    problems: list[str] = []
    if not body.strip():
        problems.append("empty body")
    known = _claim_keys(claims)
    refs = {
        token
        for token in body.replace("[", " ").replace("]", " ").split()
        if token.startswith("C") and token[1:].isdigit()
    }
    if kind != "paper_index" and not refs:
        problems.append("no claim citations")
    if known and not refs.issubset(known):
        problems.append("unknown claim refs")
    return {
        "ok": not problems,
        "problems": problems,
        "section": {
            "section_id": str(section.get("section_id") or title),
            "kind": kind,
            "title": title,
            "body": body,
            "claim_ids": sorted(refs),
        },
    }


def persist_report(
    root: str,
    title: str,
    content_md: str,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    markdown = path / "report.md"
    markdown.write_text(content_md, encoding="utf-8")
    payload = {
        "title": title,
        "content_md": content_md,
        "claims": claims or [],
        "word_count": len(content_md.split()),
    }
    json_path = path / "report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(json_path),
        "markdown_path": str(markdown),
        "word_count": payload["word_count"],
        "state": "complete",
    }


def build_report_tools(
    llm: SectionLLMPort | None = None, *, language: str = "en"
) -> list[ToolSpec]:
    tools = [
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
            "report.persist",
            "Persist a report as report.md and report.json.",
            {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "title": {"type": "string"},
                    "content_md": {"type": "string"},
                    "claims": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["root", "title", "content_md"],
            },
            {"type": "object"},
            side_effect=True,
            handler=lambda args: persist_report(
                args["root"], args["title"], args["content_md"], args.get("claims")
            ),
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
    if llm is not None:
        tools.append(
            ToolSpec(
                "report.write_section",
                "Write one evidence-grounded report section with an LLM.",
                {
                    "type": "object",
                    "properties": {
                        "section": {"type": "object"},
                        "claims": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["section", "claims"],
                },
                {"type": "object"},
                handler=lambda args: write_section(
                    args["section"], args["claims"], llm, language=language
                ),
            )
        )
    return tools
