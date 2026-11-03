"""Report workflow v2 domain tools.

The tools are deterministic at the boundaries and use the LLM only for section
writing. Each Node can still inspect, plan, check and recover through the
general toolset exposed by the workflow.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.kernel.agent.audit import LLMAuditor
from lit_agent_v2.research.openalex import OpenAlexAdapter
from lit_agent_v2.research.pdf import download_html_text, download_pdf_text
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
    titles = section.get("paper_titles") or {}
    paper_ids = [str(value) for value in section.get("paper_ids") or []]
    if not paper_ids:
        selected = claims[:6]
        return " ".join(
            f'"{claim.get("quote") or claim.get("text") or ""}" [{claim.get("claim_id")}].'
            for claim in selected
            if claim.get("quote") or claim.get("text")
        ) or "No exact-quote evidence was available for this section."
    lines: list[str] = []
    for paper_id in paper_ids:
        selected = [claim for claim in claims if str(claim.get("paper_id")) == paper_id][:2]
        if not selected:
            continue
        title = titles.get(paper_id, paper_id)
        quotes = " ".join(
            f'"{claim.get("quote") or claim.get("text") or ""}" [{claim.get("claim_id")}].'
            for claim in selected
            if claim.get("quote") or claim.get("text")
        )
        if quotes:
            lines.append(f"**[{title}](#paper-{paper_id}).** {quotes}")
    return "\n\n".join(lines) or "No exact-quote evidence was available for this section."


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
    target_papers: int | None = None,
    max_words: int = 8000,
) -> dict[str, Any]:
    papers = list(evidence.get("papers") or [])
    claims = list(evidence.get("claims") or [])
    sections = list(report.get("sections") or [])
    target = max(1, int(target_papers or len(papers) or 100))
    min_papers = max(1, min(target, 100))
    min_fulltext = max(0, min(target, int(target * 0.2)))
    papers_with_text = sum(
        1 for paper in papers if paper.get("fulltext") or paper.get("abstract")
    )
    papers_with_claims = len(
        {str(claim.get("paper_id")) for claim in claims if claim.get("paper_id")}
    )
    min_claim_papers = min(papers_with_text, max(1, int(target * 0.8))) if papers_with_text else 0
    min_claims = max(10, min_claim_papers)
    min_sections = max(3, min(10, (target + 4) // 5 + 2))
    min_words = max(800, min(3500, target * 25))
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
    if papers_with_claims < min_claim_papers:
        problems.append(
            f"papers with claims {papers_with_claims} < {min_claim_papers}"
        )
    if len(sections) < min_sections:
        problems.append(f"sections {len(sections)} < {min_sections}")
    if not min_words <= words <= max_words:
        problems.append(f"word_count {words} outside {min_words}-{max_words}")
    if coverage < 1.0:
        problems.append(f"citation_coverage {coverage:.3f} < 1.0")
    empty = 0
    unknown = 0
    section_metrics: list[dict[str, Any]] = []
    cited_claim_ids: set[str] = set()
    duplicate_sentences = 0
    seen_sentences: set[str] = set()
    for section in sections:
        body = str(section.get("body") or "")
        section_id = str(section.get("section_id") or "")
        refs = _CITATION.findall(body)
        cited_claim_ids.update(f"C{ref}" for ref in refs)
        sentences = [
            " ".join(sentence.split()).lower()
            for sentence in re.split(r"(?<=[.!?])\s+", body)
            if len(sentence.strip()) > 30
        ]
        for sentence in sentences:
            if sentence in seen_sentences:
                duplicate_sentences += 1
            seen_sentences.add(sentence)
        if section.get("kind") == "paper_index":
            continue
        checked = check_section(section, claims)
        if not body.strip():
            empty += 1
        if checked.get("problems"):
            unknown += 1
        section_metrics.append(
            {
                "section_id": section_id,
                "kind": section.get("kind"),
                "words": len(body.split()),
                "citations": len(refs),
                "claim_refs": len(set(refs)),
                "problems": checked.get("problems", []),
            }
        )
    if empty:
        problems.append(f"empty sections: {empty}")
    if unknown:
        problems.append(f"sections with reference problems: {unknown}")
    if len(sections) != len({str(section.get("section_id")) for section in sections}):
        problems.append("duplicate section ids")
    return {
        "accepted": not problems,
        "problems": problems,
        "metrics": {
            "target_papers": target,
            "papers": len(papers),
            "fulltext": fulltext,
            "claims": len(claims),
            "papers_with_text": papers_with_text,
            "papers_with_claims": papers_with_claims,
            "min_claims": min_claims,
            "min_claim_papers": min_claim_papers,
            "sections": len(sections),
            "word_count": words,
            "citation_coverage": coverage,
            "empty_sections": empty,
            "reference_problem_sections": unknown,
            "section_metrics": section_metrics,
            "cited_claims": len(cited_claim_ids),
            "uncovered_claims": max(0, len(claims) - len(cited_claim_ids)),
            "duplicate_sentences": duplicate_sentences,
        },
    }


def _download_online(paper: dict[str, Any], out_dir: Path) -> str:
    paper_id = str(paper.get("paper_id") or "")
    target = out_dir / "fulltext" / f"{paper_id}.txt"
    if target.exists() and target.stat().st_size > 500:
        return target.read_text(encoding="utf-8", errors="ignore")
    for url, fetch in (
        (str(paper.get("pdf_url") or ""), download_pdf_text),
        (str(paper.get("html_url") or ""), download_html_text),
    ):
        if not url:
            continue
        try:
            text = fetch(url)
        except Exception:  # noqa: BLE001
            continue
        if len(text.strip()) < 500:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return text
    return ""


def collect_online(
    query: str,
    out_dir: str,
    *,
    limit: int = 20,
    from_year: int | None = None,
    download_fulltext: bool = True,
) -> dict[str, Any]:
    candidates = OpenAlexAdapter().fetch(
        query, limit=min(200, max(limit * 6, limit + 60)), from_year=from_year
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    if not download_fulltext:
        for paper in candidates:
            payload = dict(paper.__dict__)
            marker = str(payload.get("paper_id") or payload.get("title") or "").strip().lower()
            if not marker or marker in seen:
                continue
            if not (payload.get("abstract") or payload.get("pdf_url") or payload.get("html_url")):
                continue
            seen.add(marker)
            accepted.append(payload)
            if len(accepted) >= limit:
                break
    else:
        # Keep searching until we have `limit` papers with usable fulltext.
        # A candidate that cannot be downloaded is skipped, not silently kept
        # as an abstract-only paper.
        batch_size = 6
        for start in range(0, len(candidates), batch_size):
            batch: list[dict[str, Any]] = []
            for paper in candidates[start : start + batch_size]:
                payload = dict(paper.__dict__)
                marker = str(payload.get("paper_id") or payload.get("title") or "").strip().lower()
                if not marker or marker in seen:
                    continue
                if not (payload.get("abstract") or payload.get("pdf_url") or payload.get("html_url")):
                    continue
                seen.add(marker)
                batch.append(payload)
            if not batch:
                continue
            with ThreadPoolExecutor(max_workers=batch_size) as pool:
                texts = list(pool.map(lambda paper: _download_online(paper, out), batch))
            for paper, text in zip(batch, texts, strict=True):
                if text:
                    paper["fulltext"] = text
                    accepted.append(paper)
                else:
                    skipped.append({"paper_id": paper.get("paper_id"), "title": paper.get("title")})
                if len(accepted) >= limit:
                    break
            if len(accepted) >= limit:
                break

    (out / "papers.jsonl").write_text(
        "\n".join(json.dumps(paper, ensure_ascii=False) for paper in accepted),
        encoding="utf-8",
    )
    fulltext = sum(1 for paper in accepted if paper.get("fulltext"))
    source_path = _write(
        out / "source.json",
        {
            "papers": accepted,
            "count": len(accepted),
            "limit": limit,
            "query": query,
            "skipped_no_fulltext": skipped,
        },
    )
    return {
        "source_path": source_path,
        "papers": len(accepted),
        "fulltext": fulltext,
        "fulltext_ratio": fulltext / len(accepted) if accepted else 0.0,
        "limit": limit,
        "skipped_no_fulltext": len(skipped),
        "state": "complete" if len(accepted) >= limit else "degraded",
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


def _paper_titles(evidence: dict[str, Any]) -> dict[str, str]:
    return {
        str(paper.get("paper_id")): str(paper.get("title") or paper.get("paper_id") or "")
        for paper in evidence.get("papers") or []
        if paper.get("paper_id")
    }


def _title_link(paper_id: str, title: str) -> str:
    label = title.replace("[", "(").replace("]", ")").strip() or paper_id
    return f"[{label}](#paper-{paper_id})"


def _link_titles(body: str, section: dict[str, Any], titles: dict[str, str]) -> str:
    for raw_id in section.get("paper_ids") or []:
        paper_id = str(raw_id)
        title = titles.get(paper_id)
        if not title or f"](#paper-{paper_id})" in body:
            continue
        link = _title_link(paper_id, title)
        pattern = rf"(?<!\[)(?<!\(){re.escape(title)}(?!\]|\()"
        body = re.sub(pattern, link, body, count=1)
    return body


def _normalize_body(
    body: str, section: dict[str, Any], titles: dict[str, str]
) -> str:
    body = body.strip()
    body = re.sub(r"^\s*#{1,6}\s+[^\n]*\n+", "", body, count=1)
    for paper_id in section.get("paper_ids") or []:
        title = titles.get(str(paper_id))
        if not title:
            continue
        body = re.sub(
            rf"(?<![A-Za-z0-9_#-]){re.escape(str(paper_id))}(?![A-Za-z0-9_])",
            _title_link(str(paper_id), title),
            body,
        )
    return re.sub(r"\n{3,}", "\n\n", body).strip()


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
    titles = _paper_titles(evidence)
    section["paper_titles"] = {
        str(pid): titles[str(pid)]
        for pid in section.get("paper_ids") or []
        if str(pid) in titles
    }
    path = Path(out_dir) / "sections" / f"{section_id}.json"
    if path.exists():
        existing = _read(path)
        if existing.get("ok"):
            return {**existing, "resumed": True}

    attempts = 0
    problems: list[str] = []
    body = ""
    fallback = False
    if section.get("kind") == "paper_index":
        body = "\n".join(
            f"- {_title_link(str(pid), title)}"
            for pid, title in titles.items()
        )
        attempts = 1
    while not body and attempts < max_attempts:
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
    body = _link_titles(_normalize_body(body, section, titles), section, titles)
    section["body"] = body
    checked = check_section(section, claims)
    if section.get("kind") == "paper_analysis":
        paper_ids = [str(pid) for pid in section.get("paper_ids") or []]
        missing_titles = [
            pid for pid in paper_ids if titles.get(pid) and titles[pid] not in body
        ]
        if missing_titles:
            body = _fallback_body(section, claims)
            section["body"] = body
            checked = check_section(section, claims)
            fallback = True
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


def _write_next_section_tool(
    args: dict[str, Any], context: Any, llm: Any
) -> dict[str, Any]:
    result = write_next_section(
        args["plan_path"],
        args["evidence_path"],
        args["out_dir"],
        llm=llm,
        language=str(args.get("language", "en")),
    )
    events = getattr(context, "events", None)
    if events is not None:
        events.emit(
            "section.written",
            section_id=result.get("section_id"),
            written=result.get("written"),
            remaining=result.get("remaining"),
            total=result.get("total"),
            ok=result.get("ok"),
        )
        if not result.get("ok"):
            events.emit(
                "section.failed",
                section_id=result.get("section_id"),
                written=result.get("written"),
                remaining=result.get("remaining"),
                total=result.get("total"),
                ok=False,
            )
    return result


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
    llm: Any | None = None,
    strict_audit: bool = False,
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
        target_papers=evidence.get("target_papers"),
    )
    if strict_quality and not quality["accepted"]:
        raise ValueError("E_REPORT_QUALITY: " + "; ".join(quality["problems"]))
    audit: dict[str, Any] | None = None
    if llm is not None:
        audit = audit_report(
            llm,
            # The report is not persisted yet; audit the draft payload.
            str(Path(out_dir) / "draft.json"),
            evidence_path,
        )
        quality["audit"] = audit
        if strict_audit and audit["status"] == "rejected":
            raise ValueError("E_REPORT_AUDIT: " + "; ".join(audit.get("problems") or []))
    persisted = persist_report(
        out_dir,
        assembled["title"],
        assembled["content_md"],
        claims,
    )
    report_payload = _read(persisted["path"])
    report_payload.update(
        {
            "target_papers": quality["metrics"].get("target_papers"),
            "papers": len(papers),
            "fulltext": fulltext,
            "fulltext_ratio": fulltext / len(papers) if papers else 0.0,
            "sections": sections,
            "state": state,
            "citation_coverage": _coverage(sections),
            "quality": quality,
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


def audit_report(llm: Any, report_path: str, evidence_path: str) -> dict[str, Any]:
    report = _read(report_path)
    evidence = _read(evidence_path)
    quality = check_report_quality(report, evidence)
    metrics = quality["metrics"]
    summary = (
        f"papers={metrics['papers']}; fulltext={metrics['fulltext']}; "
        f"claims={metrics['claims']}; sections={metrics['sections']}; "
        f"words={metrics['word_count']}; citation_coverage={metrics['citation_coverage']}; "
        f"empty_sections={metrics['empty_sections']}; "
        f"uncovered_claims={metrics['uncovered_claims']}; "
        f"duplicate_sentences={metrics['duplicate_sentences']}; "
        f"quality_accepted={quality['accepted']}"
    )
    report_audit = LLMAuditor(llm, min_score=1.0).audit_summary(summary)
    if report_audit.accepted:
        status = "accepted"
    elif report_audit.problems and not report_audit.problems[0].startswith("audit_error"):
        status = "rejected"
    else:
        status = "unavailable"
    return {
        "accepted": report_audit.accepted,
        "status": status,
        "scores": report_audit.scores,
        "problems": report_audit.problems,
        "summary": summary,
        "quality_accepted": quality["accepted"],
    }


def build_report_v2_tools(llm: Any | None = None) -> list[ToolSpec]:
    return [
        ToolSpec(
            "source.collect_online",
            "Search OpenAlex, download open PDF/HTML fulltext, and write a local corpus.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "limit": {"type": "integer"},
                    "from_year": {"type": "integer"},
                    "download_fulltext": {"type": "boolean"},
                },
                "required": ["query", "out_dir"],
            },
            side_effect=True,
            timeout_s=900.0,
            handler=lambda args: collect_online(
                args["query"],
                args["out_dir"],
                limit=int(args.get("limit", 20)),
                from_year=args.get("from_year"),
                download_fulltext=bool(args.get("download_fulltext", True)),
            ),
        ),
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
                args["root"], args["out_dir"], int(args.get("limit", 20))
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
            context_handler=lambda args, context: _write_next_section_tool(
                {**args, "language": str(args.get("language", "en"))},
                context,
                llm,
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
            "report.quality.metrics",
            "Return section-level report quality metrics without enforcing the gate.",
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
            )["metrics"],
        ),
        ToolSpec(
            "report.quality.audit",
            "Audit a report using compact quality metrics (advisory).",
            {
                "type": "object",
                "properties": {
                    "report_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                },
                "required": ["report_path", "evidence_path"],
            },
            handler=lambda args: (
                audit_report(llm, args["report_path"], args["evidence_path"])
                if llm is not None
                else {"accepted": False, "problems": ["audit_llm_unavailable"]}
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
                    "strict_audit": {"type": "boolean"},
                },
                "required": ["draft_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=120.0,
            handler=lambda args: finalize_report(
                args["draft_path"],
                args["evidence_path"],
                args["out_dir"],
                strict_quality=True,
                llm=llm,
                strict_audit=True,
            ),
        ),
    ]
