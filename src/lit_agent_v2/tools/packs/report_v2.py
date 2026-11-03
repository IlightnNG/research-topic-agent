"""Report workflow v2 domain tools.

The tools are deterministic at the boundaries and use the LLM only for section
writing. Each Node can still inspect, plan, check and recover through the
general toolset exposed by the workflow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.tools.packs.demo import (
    collect_source,
    extract_evidence,
    finalize_demo,
)
from lit_agent_v2.tools.packs.report import (
    assemble_report,
    check_section,
    persist_report,
    plan_report,
    write_section,
)

__all__ = ["build_report_v2_tools"]

_CITATION = re.compile(r"\[C(\d+)\]")


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str | Path, value: Any) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def _fallback_body(section: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    paper_ids = [str(value) for value in section.get("paper_ids") or []]
    selected = [
        claim
        for claim in claims
        if not paper_ids or str(claim.get("paper_id")) in paper_ids
    ][:6]
    if not selected:
        return "No exact-quote evidence was available for this section."
    lines = []
    for claim in selected:
        quote = str(claim.get("quote") or claim.get("text") or "").strip()
        if quote:
            lines.append(f'"{quote}" [{claim.get("claim_id")}].')
    return " ".join(lines) if lines else "No exact-quote evidence was available."


def _coverage(sections: list[dict[str, Any]]) -> float:
    body_sections = [s for s in sections if s.get("kind") != "paper_index"]
    if not body_sections:
        return 0.0
    cited = sum(1 for section in body_sections if _CITATION.search(str(section.get("body") or "")))
    return cited / len(body_sections)


def check_report_quality(
    report: dict[str, Any],
    evidence: dict[str, Any],
    *,
    min_papers: int = 100,
    min_fulltext: int = 35,
    min_claims: int = 100,
    min_sections: int = 10,
    min_words: int = 3500,
    max_words: int = 8000,
) -> dict[str, Any]:
    papers = list(evidence.get("papers") or [])
    claims = list(evidence.get("claims") or [])
    sections = list(report.get("sections") or [])
    fulltext = sum(1 for paper in papers if paper.get("fulltext"))
    body = str(report.get("content_md") or "")
    words = len(body.split())
    coverage = _coverage(sections)
    problems: list[str] = []
    if len(papers) < min_papers:
        problems.append(f"papers {len(papers)} < {min_papers}")
    if fulltext < min_fulltext and report.get("state") != "degraded":
        problems.append(f"fulltext {fulltext} < {min_fulltext} and state is not degraded")
    if len(claims) < min_claims:
        problems.append(f"claims {len(claims)} < {min_claims}")
    if len(sections) < min_sections:
        problems.append(f"sections {len(sections)} < {min_sections}")
    if not min_words <= words <= max_words:
        problems.append(f"word_count {words} outside {min_words}-{max_words}")
    if coverage < 1.0:
        problems.append(f"citation_coverage {coverage:.3f} < 1.0")
    empty = 0
    unknown = 0
    for section in sections:
        if section.get("kind") == "paper_index":
            continue
        checked = check_section(section, claims)
        if not str(section.get("body") or "").strip():
            empty += 1
        if checked.get("problems"):
            unknown += 1
    if empty:
        problems.append(f"empty sections: {empty}")
    if unknown:
        problems.append(f"sections with reference problems: {unknown}")
    return {
        "accepted": not problems,
        "problems": problems,
        "metrics": {
            "papers": len(papers),
            "fulltext": fulltext,
            "claims": len(claims),
            "sections": len(sections),
            "word_count": words,
            "citation_coverage": coverage,
            "empty_sections": empty,
            "reference_problem_sections": unknown,
        },
    }


def plan_from_evidence(evidence_path: str, out_dir: str) -> dict[str, Any]:
    evidence = _read(evidence_path)
    papers = list(evidence.get("papers") or [])
    claims = list(evidence.get("claims") or [])
    plan = plan_report(papers, chunk_size=5)
    path = _write(Path(out_dir) / "plan.json", plan)
    sections = list(plan.get("sections") or [])
    covered = {
        str(claim.get("paper_id"))
        for claim in claims
        if claim.get("paper_id")
    }
    return {
        "plan_path": path,
        "sections": len(sections),
        "section_ids": [section.get("section_id") for section in sections],
        "papers_covered": len(covered),
        "coverage": len(covered) / len(papers) if papers else 0.0,
    }


def write_one_section(
    plan_path: str,
    section_id: str,
    evidence_path: str,
    out_dir: str,
    *,
    llm: Any | None,
    language: str = "en",
    max_attempts: int = 3,
) -> dict[str, Any]:
    plan = _read(plan_path)
    evidence = _read(evidence_path)
    claims = list(evidence.get("claims") or [])
    section = next(
        (
            dict(item)
            for item in plan.get("sections") or []
            if str(item.get("section_id")) == section_id
        ),
        None,
    )
    if section is None:
        raise ValueError(f"unknown section: {section_id}")
    path = Path(out_dir) / "sections" / f"{section_id}.json"
    if path.exists():
        existing = _read(path)
        if existing.get("ok"):
            return {**existing, "resumed": True}

    attempts = 0
    problems: list[str] = []
    body = ""
    fallback = False
    while attempts < max_attempts:
        attempts += 1
        if llm is None:
            break
        try:
            result = write_section(section, claims, llm, language=language)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{type(exc).__name__}: {exc}")
            continue
        problems = [str(item) for item in result.get("problems") or []]
        candidate = str((result.get("section") or {}).get("body") or "")
        if result.get("ok") and candidate:
            body = candidate
            break
        if candidate:
            body = candidate
    if not body:
        body = _fallback_body(section, claims)
        fallback = True
    section["body"] = body
    checked = check_section(section, claims)
    if not checked.get("ok") and section.get("kind") != "paper_index":
        body = _fallback_body(section, claims)
        section["body"] = body
        fallback = True
        checked = check_section(section, claims)
    is_index = section.get("kind") == "paper_index"
    payload = {
        "section_id": section_id,
        "kind": section.get("kind"),
        "title": section.get("title"),
        "body": body,
        "claim_ids": checked.get("refs", []),
        "attempts": attempts,
        "ok": bool(checked.get("ok")) or is_index,
        "problems": [] if is_index else checked.get("problems", []),
        "fallback": fallback,
    }
    _write(path, payload)
    return {**payload, "section_path": str(path), "resumed": False}


def section_progress(plan_path: str, out_dir: str) -> dict[str, Any]:
    plan = _read(plan_path)
    section_ids = [str(item.get("section_id")) for item in plan.get("sections") or []]
    written: list[str] = []
    failed: list[str] = []
    for section_id in section_ids:
        path = Path(out_dir) / "sections" / f"{section_id}.json"
        if not path.exists():
            continue
        payload = _read(path)
        if payload.get("ok"):
            written.append(section_id)
        else:
            failed.append(section_id)
    remaining = [section_id for section_id in section_ids if section_id not in written]
    return {
        "total": len(section_ids),
        "written": len(written),
        "remaining": len(remaining),
        "next_section": remaining[0] if remaining else None,
        "done": not remaining,
        "failed": failed,
    }


def write_next_section(
    plan_path: str,
    evidence_path: str,
    out_dir: str,
    *,
    llm: Any | None,
    language: str = "en",
) -> dict[str, Any]:
    progress = section_progress(plan_path, out_dir)
    next_section = progress.get("next_section")
    if next_section is None:
        return {**progress, "section_path": None, "ok": True}
    result = write_one_section(
        plan_path,
        str(next_section),
        evidence_path,
        out_dir,
        llm=llm,
        language=language,
    )
    after = section_progress(plan_path, out_dir)
    return {
        **after,
        "section_path": result.get("section_path"),
        "section_id": next_section,
        "attempts": result.get("attempts"),
        "fallback": result.get("fallback"),
        "ok": bool(result.get("ok")),
    }


def assemble_sections(plan_path: str, evidence_path: str, out_dir: str) -> dict[str, Any]:
    plan = _read(plan_path)
    evidence = _read(evidence_path)
    claims = list(evidence.get("claims") or [])
    sections: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw in plan.get("sections") or []:
        section_id = str(raw.get("section_id"))
        path = Path(out_dir) / "sections" / f"{section_id}.json"
        if not path.exists():
            missing.append(section_id)
            continue
        payload = _read(path)
        if not payload.get("ok"):
            missing.append(section_id)
            continue
        sections.append(
            {
                "section_id": section_id,
                "kind": raw.get("kind"),
                "title": raw.get("title"),
                "body": payload.get("body", ""),
                "claim_ids": payload.get("claim_ids", []),
            }
        )
    if missing:
        raise ValueError("missing or failed sections: " + ", ".join(missing))
    draft = assemble_report("Report", sections)
    draft["sections"] = sections
    draft["claims"] = claims
    draft["papers"] = len(evidence.get("papers") or [])
    draft["citation_coverage"] = _coverage(sections)
    path = _write(Path(out_dir) / "draft.json", draft)
    return {
        "draft_path": path,
        "sections": len(sections),
        "word_count": draft["word_count"],
        "citation_coverage": draft["citation_coverage"],
    }


def write_report(
    plan_path: str,
    evidence_path: str,
    out_dir: str,
    *,
    llm: Any | None,
    language: str = "en",
) -> dict[str, Any]:
    plan = _read(plan_path)
    retried = 0
    fallback_sections = 0
    for raw in plan.get("sections") or []:
        result = write_one_section(
            plan_path,
            str(raw.get("section_id")),
            evidence_path,
            out_dir,
            llm=llm,
            language=language,
        )
        if int(result.get("attempts", 1)) > 1:
            retried += 1
        if result.get("fallback"):
            fallback_sections += 1
    assembled = assemble_sections(plan_path, evidence_path, out_dir)
    return {
        **assembled,
        "sections_retried": retried,
        "fallback_sections": fallback_sections,
    }


def finalize_report(
    draft_path: str,
    evidence_path: str,
    out_dir: str,
    *,
    strict_quality: bool = False,
) -> dict[str, Any]:
    draft = _read(draft_path)
    evidence = _read(evidence_path)
    sections = list(draft.get("sections") or [])
    claims = list(evidence.get("claims") or [])
    problems = []
    for section in sections:
        if section.get("kind") == "paper_index":
            continue
        checked = check_section(section, claims)
        if not checked.get("ok"):
            problems.append(f"{section.get('section_id')}: {checked.get('problems')}")
    if problems:
        raise ValueError("; ".join(problems))
    assembled = assemble_report(
        str(draft.get("title") or "Report"),
        sections,
        state=str(draft.get("state") or "complete"),
    )
    papers = list(evidence.get("papers") or [])
    fulltext = sum(1 for paper in papers if paper.get("fulltext"))
    state = "complete" if papers and fulltext / len(papers) >= 0.3 else "degraded"
    quality = check_report_quality(
        {
            "papers": len(papers),
            "content_md": assembled["content_md"],
            "sections": sections,
            "state": state,
        },
        evidence,
    )
    if strict_quality and not quality["accepted"]:
        raise ValueError("E_REPORT_QUALITY: " + "; ".join(quality["problems"]))
    persisted = persist_report(
        out_dir,
        assembled["title"],
        assembled["content_md"],
        claims,
    )
    report_payload = _read(persisted["path"])
    report_payload.update(
        {
            "papers": len(papers),
            "fulltext": fulltext,
            "fulltext_ratio": fulltext / len(papers) if papers else 0.0,
            "sections": sections,
            "state": state,
            "citation_coverage": _coverage(sections),
        }
    )
    _write(persisted["path"], report_payload)
    final = finalize_demo(persisted["path"], out_dir)
    final["papers"] = len(papers)
    final["sections"] = len(sections)
    final["word_count"] = persisted["word_count"]
    final["state"] = state
    final["citation_coverage"] = _coverage(sections)
    final["quality"] = quality
    final["report_path"] = persisted["path"]
    final["markdown_path"] = persisted["markdown_path"]
    final["path"] = persisted["markdown_path"]
    _write(Path(out_dir) / "final.json", final)
    return final


def build_report_v2_tools(llm: Any | None = None) -> list[ToolSpec]:
    return [
        ToolSpec(
            "source.collect",
            "Collect a local corpus, deduplicate papers and write source.json.",
            {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["root", "out_dir"],
            },
            side_effect=True,
            timeout_s=60.0,
            handler=lambda args: collect_source(
                args["root"], args["out_dir"], int(args.get("limit", 100))
            ),
        ),
        ToolSpec(
            "evidence.extract",
            "Extract exact-quote claims and write evidence.json.",
            {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["source_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=120.0,
            handler=lambda args: extract_evidence(args["source_path"], args["out_dir"]),
        ),
        ToolSpec(
            "report.plan_v2",
            "Build a report plan from evidence and write plan.json.",
            {
                "type": "object",
                "properties": {
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=30.0,
            handler=lambda args: plan_from_evidence(args["evidence_path"], args["out_dir"]),
        ),
        ToolSpec(
            "report.section_status",
            "Return the next unwritten section for the report.write loop.",
            {
                "type": "object",
                "properties": {
                    "plan_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["plan_path", "out_dir"],
            },
            handler=lambda args: section_progress(args["plan_path"], args["out_dir"]),
            repeatable=True,
        ),
        ToolSpec(
            "report.write_next_section",
            "Write the next unwritten section. Repeat until done=true, then assemble.",
            {
                "type": "object",
                "properties": {
                    "plan_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["plan_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=180.0,
            handler=lambda args: write_next_section(
                args["plan_path"],
                args["evidence_path"],
                args["out_dir"],
                llm=llm,
                language=str(args.get("language", "en")),
            ),
            repeatable=True,
        ),
        ToolSpec(
            "report.write_section_v2",
            "Write one planned section with local retries and persist sections/{id}.json.",
            {
                "type": "object",
                "properties": {
                    "plan_path": {"type": "string"},
                    "section_id": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["plan_path", "section_id", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=180.0,
            handler=lambda args: write_one_section(
                args["plan_path"],
                args["section_id"],
                args["evidence_path"],
                args["out_dir"],
                llm=llm,
                language=str(args.get("language", "en")),
            ),
        ),
        ToolSpec(
            "report.check_section_v2",
            "Check one persisted section file for citations and empty body.",
            {
                "type": "object",
                "properties": {
                    "section_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                },
                "required": ["section_path", "evidence_path"],
            },
            handler=lambda args: check_section(
                _read(args["section_path"]),
                list(_read(args["evidence_path"]).get("claims") or []),
            ),
        ),
        ToolSpec(
            "report.assemble_v2",
            "Assemble persisted section files into draft.json.",
            {
                "type": "object",
                "properties": {
                    "plan_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["plan_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=30.0,
            handler=lambda args: assemble_sections(
                args["plan_path"], args["evidence_path"], args["out_dir"]
            ),
        ),
        ToolSpec(
            "report.quality.check",
            "Check report quality metrics and citation/reference safety.",
            {
                "type": "object",
                "properties": {
                    "report_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                },
                "required": ["report_path", "evidence_path"],
            },
            handler=lambda args: check_report_quality(
                _read(args["report_path"]), _read(args["evidence_path"])
            ),
        ),
        ToolSpec(
            "report.write_v2",
            "Write all planned sections and write draft.json. Falls back to deterministic evidence text.",
            {
                "type": "object",
                "properties": {
                    "plan_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["plan_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=600.0,
            handler=lambda args: write_report(
                args["plan_path"],
                args["evidence_path"],
                args["out_dir"],
                llm=llm,
                language=str(args.get("language", "en")),
            ),
        ),
        ToolSpec(
            "report.finalize_v2",
            "Check sections, assemble, persist and hash the final report.",
            {
                "type": "object",
                "properties": {
                    "draft_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "strict_quality": {"type": "boolean"},
                },
                "required": ["draft_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=60.0,
            handler=lambda args: finalize_report(
                args["draft_path"],
                args["evidence_path"],
                args["out_dir"],
                strict_quality=bool(args.get("strict_quality", True)),
            ),
        ),
    ]
