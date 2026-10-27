"""报告组装 + 硬校验（3.2 / S6）。

规则：正文 section 必须有 claim；`[C#]` 必须能映射到 claims；不合法就回落模板。
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent.config import Settings
from lit_agent.models.report import Report, ReportSection
from lit_agent.report.context import ReportContext, build_context
from lit_agent.report.synthesis import DirectionInsight, synthesize_all

__all__ = ["ValidationResult", "assemble_report", "build_report_v2", "validate_report"]

logger = logging.getLogger(__name__)
_CITE = re.compile(r"\[C(\d+)\]")


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _refs(item: Any, index_of: dict[str, int]) -> str:
    refs = [index_of[cid] + 1 for cid in item.claim_ids if cid in index_of][:2]
    return " ".join(f"[C{index}]" for index in refs)


def _section_body(insight: DirectionInsight, index_of: dict[str, int]) -> tuple[str, list[int]]:
    lines: list[str] = []
    claim_ids: list[str] = []
    if insight.definition:
        lines.append(insight.definition)
    for title, items in (
        ("Common ground:", insight.common_ground),
        ("Differences:", insight.differences),
        ("Open questions:", insight.open_questions),
    ):
        if not items:
            continue
        lines.append(title)
        for item in items:
            lines.append(f"- {item.text} {_refs(item, index_of)}".strip())
            claim_ids.extend(item.claim_ids)
    return "\n".join(lines), claim_ids


def _build_sections(
    context: ReportContext,
    insights: list[DirectionInsight],
    *,
    index_of: dict[str, int],
    period: str | None,
    language: str,
) -> list[ReportSection]:
    sections: list[ReportSection] = []
    cards = context.cards
    claims = context.claim_set.claims
    overview = (
        f"{len(cards)} papers, {len(claims)} claims, {len(context.directions)} directions."
        + (f" Period: {period}." if period else "")
    )
    sections.append(ReportSection(id="overview", title="Overview", body=overview, kind="overview"))

    for insight in insights:
        body, claim_ids = _section_body(insight, index_of)
        indexes = sorted({index_of[cid] for cid in claim_ids if cid in index_of})
        sections.append(
            ReportSection(
                id=insight.direction_id,
                title=insight.name,
                body=body,
                claim_indexes=indexes,
                kind="deep_dive",
            )
        )

    if context.meta.get("duplicates") or context.meta.get("failed_papers") or context.meta.get("dropped_claims"):
        sections.append(
            ReportSection(
                id="gaps",
                title="Gaps & Next Steps",
                body=(
                    f"duplicates={context.meta.get('duplicates', 0)}; "
                    f"dropped_claims={context.meta.get('dropped_claims', 0)}; "
                    f"failed_papers={len(context.meta.get('failed_papers') or [])}"
                ),
                kind="gaps",
            )
        )

    if cards:
        rows = ["| paper | title | claims |", "|---|---|---|"]
        by_paper = context.claim_set.by_paper()
        for card in cards:
            rows.append(f"| {card.paper_id} | {card.title[:80]} | {len(by_paper.get(card.paper_id, []))} |")
        sections.append(
            ReportSection(id="index", title="Paper Index", body="\n".join(rows), kind="paper_index")
        )
    return sections


def validate_report(report: Report, *, language: str = "en") -> ValidationResult:
    errors: list[str] = []
    seen_claims: set[int] = set()
    for section in report.sections:
        if section.kind in {"overview", "gaps", "paper_index"}:
            continue
        if not section.claim_indexes:
            errors.append(f"{section.id}: no claim_indexes")
        for index in section.claim_indexes:
            if index < 0 or index >= len(report.claims):
                errors.append(f"{section.id}: claim index {index} out of range")
            seen_claims.add(index)
        for match in _CITE.finditer(section.body):
            index = int(match.group(1)) - 1
            if index < 0 or index >= len(report.claims):
                errors.append(f"{section.id}: [C{index + 1}] unresolved")
    if report.language != language:
        errors.append("language mismatch")
    return ValidationResult(ok=not errors, errors=errors)


def assemble_report(
    *,
    run_id: str,
    topic_id: str,
    title: str,
    period: str | None,
    context: ReportContext,
    insights: list[DirectionInsight],
    language: str,
    generated_by: str,
) -> Report:
    index_of = {
        claim.claim_id: index
        for index, claim in enumerate(context.claim_set.claims)
        if claim.claim_id
    }
    sections = _build_sections(
        context, insights, index_of=index_of, period=period, language=language
    )
    body = f"# {title}\n\n" + "\n\n".join(f"## {s.title}\n{s.body}" for s in sections)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    return Report(
        report_id=f"{run_id}:{digest}",
        topic_id=topic_id,
        run_id=run_id,
        period=period,
        title=title,
        content_md=body,
        content_sha=digest,
        claims=context.claim_set.claims,
        sections=sections,
        n_claims=len(context.claim_set.claims),
        degraded=not context.cards,
        language=language,
        generated_by=generated_by,
        word_count=_word_count(body),
    )


def build_report_v2(
    settings: Settings,
    *,
    run_id: str,
    topic_id: str,
    paper_ids: list[str],
    title: str,
    period: str | None = None,
    gateway: Any | None = None,
) -> Report:
    language = settings.report.language
    context = build_context(settings, paper_ids, gateway=gateway)
    insights = synthesize_all(
        context.directions,
        context.claim_set.claims,
        gateway=gateway if settings.report.synthesis else None,
        language=language,
    )
    report = assemble_report(
        run_id=run_id,
        topic_id=topic_id,
        title=title,
        period=period,
        context=context,
        insights=insights,
        language=language,
        generated_by="llm" if settings.report.synthesis and gateway else "template",
    )
    check = validate_report(report, language=language)
    if not check.ok:
        logger.warning("report.validate.fallback", extra={"errors": check.errors[:3]})
        report = assemble_report(
            run_id=run_id,
            topic_id=topic_id,
            title=title,
            period=period,
            context=context,
            insights=[],
            language=language,
            generated_by="template",
        )
        report = report.model_copy(update={"fallback_reason": "; ".join(check.errors[:3])})
    logger.info(
        "report.v2.built",
        extra={
            "papers": len(context.cards),
            "claims": report.n_claims,
            "sections": len(report.sections),
            "words": report.word_count,
            "generated_by": report.generated_by,
        },
    )
    return report
