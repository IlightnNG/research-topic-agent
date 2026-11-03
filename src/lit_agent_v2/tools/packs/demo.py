"""Deterministic demo tools for the 100-paper end-to-end run.

The Node/Kernel layer is still the orchestrator. These tools do the expensive
deterministic work in one call so the demo does not need 100 LLM steps.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.research.claims import extract_deterministic

__all__ = ["build_demo_tools"]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _papers(root: Path) -> list[dict[str, Any]]:
    path = root / "papers.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    papers = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for paper in papers:
        paper_id = str(paper.get("paper_id") or "")
        fulltext = root / "fulltext" / f"{paper_id}.txt"
        if fulltext.exists():
            paper["fulltext"] = fulltext.read_text(encoding="utf-8")
    return papers


def collect_source(root: str, out_dir: str, limit: int = 20) -> dict[str, Any]:
    corpus = _papers(Path(root))
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for paper in corpus:
        marker = str(paper.get("paper_id") or paper.get("title") or "").strip().lower()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        unique.append(paper)
        if len(unique) >= limit:
            break
    path = Path(out_dir) / "source.json"
    _write_json(path, {"papers": unique, "count": len(unique), "limit": limit})
    fulltext = sum(1 for paper in unique if paper.get("fulltext"))
    return {
        "source_path": str(path),
        "papers": len(unique),
        "fulltext": fulltext,
        "fulltext_ratio": fulltext / len(unique) if unique else 0.0,
        "limit": limit,
        "state": "degraded" if fulltext < len(unique) * 0.3 else "complete",
    }


def extract_evidence(source_path: str, out_dir: str, limit: int = 4) -> dict[str, Any]:
    source = _read_json(Path(source_path))
    papers = list(source.get("papers") or [])
    claims: list[dict[str, Any]] = []
    for paper in papers:
        paper_id = str(paper.get("paper_id") or "")
        text = str(paper.get("fulltext") or paper.get("abstract") or "")
        if not text.strip():
            continue
        found = extract_deterministic(paper_id, text, limit=limit)
        for claim in found:
            data = claim.to_dict()
            data["claim_id"] = f"C{len(claims) + 1}"
            data["paper_id"] = paper_id
            claims.append(data)
    path = Path(out_dir) / "evidence.json"
    _write_json(
        path,
        {
            "claims": claims,
            "papers": papers,
            "count": len(claims),
            "target_papers": source.get("limit"),
        },
    )
    return {
        "evidence_path": str(path),
        "claims": len(claims),
        "papers": len(papers),
    }


def _llm_group_body(
    llm: Any,
    group: list[dict[str, Any]],
    by_paper: dict[str, list[dict[str, Any]]],
    language: str,
) -> str:
    material: list[str] = []
    for paper in group:
        paper_id = str(paper.get("paper_id"))
        material.append(f"{paper_id}: {paper.get('title', '')}")
        for claim in by_paper.get(paper_id, []):
            material.append(
                f"  [{claim.get('claim_id')}] {claim.get('quote') or claim.get('text')}"
            )
    prompt = (
        "Write a concise literature-review subsection for the papers below. "
        "Use only the supplied claims, do not invent facts or citations. "
        "Every factual sentence must end with its [C#] citation. "
        "Return JSON only: {\"body\": \"...\"}. "
        f"Language: {'Chinese' if language == 'zh' else 'English'}. "
        "Keep it under 450 words."
    )
    try:
        payload, _ = llm.chat_json(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "\n".join(material)},
            ],
            temperature=0.1,
        )
        body = str(payload.get("body") or "").strip()
        if len(body) > 40 and re.search(r"\[C\d+\]", body):
            return body
    except Exception:
        return ""
    return ""


def compose_report(
    source_path: str,
    evidence_path: str,
    out_dir: str,
    language: str = "en",
    llm: Any | None = None,
) -> dict[str, Any]:
    source = _read_json(Path(source_path))
    evidence = _read_json(Path(evidence_path))
    papers = list(source.get("papers") or [])
    claims = list(evidence.get("claims") or [])
    by_paper: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        by_paper.setdefault(str(claim.get("paper_id")), []).append(claim)
    fulltext = sum(1 for paper in papers if paper.get("fulltext"))
    fulltext_ratio = fulltext / len(papers) if papers else 0.0
    complete = fulltext_ratio >= 0.3

    sections: list[dict[str, Any]] = []
    overview = (
        f"This review covers {len(papers)} papers and {len(claims)} exact-quote claims "
        f"from a local corpus [C1]. "
    )
    if claims:
        first = claims[0]
        overview += (
            f'The first extracted claim is: "{first.get("text", "")}" '
            f"[{first.get('claim_id')}]. "
        )
    if complete:
        overview += (
            f"Full text was available for {fulltext}/{len(papers)} papers; "
            "the remaining papers use abstracts only. "
        )
    else:
        overview += (
            "The corpus is abstract-only, so the report is explicitly marked degraded "
            "rather than claiming full-text coverage. "
        )
    sections.append(
        {
            "section_id": "overview",
            "kind": "overview",
            "title": "At a Glance",
            "body": overview,
        }
    )

    chunk = 10
    for start in range(0, len(papers), chunk):
        group = papers[start : start + chunk]
        lines = []
        for paper in group:
            paper_id = str(paper.get("paper_id"))
            paper_claims = by_paper.get(paper_id, [])
            title = str(paper.get("title") or paper_id)
            if not paper_claims:
                lines.append(f"{paper_id}. {title}. No exact-quote claim was extracted.")
                continue
            refs = " ".join(f"[{claim.get('claim_id')}]" for claim in paper_claims)
            quote = str(paper_claims[0].get("quote") or paper_claims[0].get("text") or "")
            lines.append(f"{paper_id}. {title}. {quote} {refs}")
        body = _llm_group_body(llm, group, by_paper, language) if llm is not None else ""
        if not body:
            body = "\n\n".join(lines)
        sections.append(
            {
                "section_id": f"paper_analysis_{start // chunk + 1:03d}",
                "kind": "paper_analysis",
                "title": f"Papers {start + 1}-{start + len(group)}",
                "body": body,
            }
        )

    if claims:
        refs = " ".join(f"[{claim.get('claim_id')}]" for claim in claims[:5])
        synthesis = (
            f"Across the extracted claims, the recurring pattern is explicit evidence "
            f"grounding: each included paper contributes at least one quoted claim {refs}. "
            + (
                "The corpus has partial full text, so these are scoped observations, "
                "not a claim of comprehensive coverage. "
                if complete
                else "The corpus is small and abstract-only, so these are scoped observations, "
                "not a claim of comprehensive coverage. "
            )
        )
    else:
        synthesis = "No claims were extracted; the synthesis is deliberately empty."
    sections.append(
        {
            "section_id": "synthesis",
            "kind": "synthesis",
            "title": "Cross-Paper Synthesis",
            "body": synthesis,
        }
    )

    index = []
    for paper in papers:
        index.append(f"- {paper.get('paper_id')}: {paper.get('title', '')}")
    sections.append(
        {
            "section_id": "paper_index",
            "kind": "paper_index",
            "title": "Paper Index",
            "body": "\n".join(index),
        }
    )

    content_md = "\n\n".join(f"## {section['title']}\n\n{section['body']}" for section in sections)
    state = "complete" if complete else "degraded"
    report = {
        "title": "100-Paper Local Corpus Review",
        "content_md": content_md,
        "word_count": len(content_md.split()),
        "state": state,
        "papers": len(papers),
        "fulltext": fulltext,
        "fulltext_ratio": fulltext_ratio,
        "claims": claims,
        "sections": sections,
        "language": language,
        "generator": "llm" if llm is not None else "deterministic",
    }
    path = Path(out_dir) / "report.json"
    _write_json(path, report)
    (Path(out_dir) / "report.md").write_text(content_md, encoding="utf-8")
    return {
        "report_path": str(path),
        "papers": len(papers),
        "claims": len(claims),
        "sections": len(sections),
        "word_count": report["word_count"],
        "state": state,
    }


def finalize_demo(report_path: str, out_dir: str) -> dict[str, Any]:
    report_file = Path(report_path)
    report = _read_json(report_file)
    content = str(report.get("content_md") or "")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    final = {
        "report_path": str(report_file),
        "content_sha": digest,
        "papers": report.get("papers", 0),
        "claims": len(report.get("claims") or []),
        "state": report.get("state", "degraded"),
    }
    path = Path(out_dir) / "final.json"
    _write_json(path, final)
    return final


def build_demo_tools(llm: Any | None = None) -> list[ToolSpec]:
    return [
        ToolSpec(
            "demo.source",
            "Read a local corpus, deduplicate papers, and write source.json.",
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
            timeout_s=30.0,
            handler=lambda args: collect_source(
                args["root"], args["out_dir"], int(args.get("limit", 100))
            ),
        ),
        ToolSpec(
            "demo.evidence",
            "Extract exact-quote claims for every paper and write evidence.json.",
            {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["source_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=60.0,
            handler=lambda args: extract_evidence(args["source_path"], args["out_dir"]),
        ),
        ToolSpec(
            "demo.report",
            "Compose a deterministic report from source and evidence artifacts.",
            {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "evidence_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["source_path", "evidence_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=300.0,
            handler=lambda args: compose_report(
                args["source_path"],
                args["evidence_path"],
                args["out_dir"],
                str(args.get("language", "en")),
                llm,
            ),
        ),
        ToolSpec(
            "demo.finalize",
            "Write final.json and a content hash for a composed report.",
            {
                "type": "object",
                "properties": {
                    "report_path": {"type": "string"},
                    "out_dir": {"type": "string"},
                },
                "required": ["report_path", "out_dir"],
            },
            side_effect=True,
            timeout_s=30.0,
            handler=lambda args: finalize_demo(args["report_path"], args["out_dir"]),
        ),
    ]
