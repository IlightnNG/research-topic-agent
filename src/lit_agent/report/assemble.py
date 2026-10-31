"""报告组装 + 硬校验（3.2 / S6）。

规则：正文 section 必须有 claim；`[C#]` 必须能映射到 claims；不合法就回落模板。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
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


_LABELS = {
    "en": {
        "overview": "Overview",
        "gaps": "Gaps & Next Steps",
        "index": "Paper Index",
        "common": "Common ground:",
        "differences": "Differences:",
        "questions": "Open questions:",
        "papers": "papers",
        "claims": "claims",
        "directions": "directions",
        "paper": "paper",
        "title": "title",
        "duplicates": "duplicates",
        "dropped": "dropped_claims",
        "failed": "failed_papers",
        "comparison": "Comparison Matrix",
        "themes": "Cross-cutting Themes",
        "direction": "Direction",
        "claims_n": "Claims",
        "representative": "Representative",
    },
    "zh": {
        "overview": "概览",
        "gaps": "缺口与下一步",
        "index": "论文索引",
        "common": "共同点：",
        "differences": "差异点：",
        "questions": "开放问题：",
        "papers": "篇论文",
        "claims": "条结论",
        "directions": "个方向",
        "paper": "论文",
        "title": "标题",
        "duplicates": "重复",
        "dropped": "丢弃结论",
        "failed": "失败论文",
        "comparison": "对比矩阵",
        "themes": "跨方向主题",
        "direction": "方向",
        "claims_n": "结论数",
        "representative": "代表论文",
    },
}


def _labels(language: str) -> dict[str, str]:
    return _LABELS.get(language, _LABELS["en"])


def _refs(item: Any, index_of: dict[str, int]) -> str:
    refs = [index_of[cid] + 1 for cid in item.claim_ids if cid in index_of][:2]
    return " ".join(f"[C{index}]" for index in refs)


def _section_body(
    insight: DirectionInsight, index_of: dict[str, int], language: str
) -> tuple[str, list[int]]:
    labels = _labels(language)
    lines: list[str] = []
    claim_ids: list[str] = []
    if insight.definition:
        lines.append(insight.definition)
    for title, items in (
        (labels["common"], insight.common_ground),
        (labels["differences"], insight.differences),
        (labels["questions"], insight.open_questions),
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
    labels = _labels(language)
    overview = (
        f"{len(cards)} {labels['papers']}, {len(claims)} {labels['claims']},"
        f" {len(context.directions)} {labels['directions']}."
        + (f" Period: {period}." if period else "")
    )
    sections.append(
        ReportSection(id="overview", title=labels["overview"], body=overview, kind="overview")
    )

    if insights:
        rows = [
            f"| {labels['direction']} | {labels['papers']} | {labels['claims_n']} | {labels['representative']} |",
            "|---|---|---|---|",
        ]
        all_indexes: list[int] = []
        by_id = {card.paper_id: card for card in cards}
        for insight in insights:
            direction = next((item for item in context.directions if item.id == insight.direction_id), None)
            paper_ids = direction.paper_ids if direction else []
            claim_ids = [cid for item in (insight.common_ground + insight.differences + insight.open_questions) for cid in item.claim_ids]
            indexes = sorted({index_of[cid] for cid in claim_ids if cid in index_of})
            all_indexes.extend(indexes)
            representative = by_id[paper_ids[0]].title[:60] if paper_ids and paper_ids[0] in by_id else "-"
            rows.append(
                f"| {insight.name} | {len(paper_ids)} | {len(indexes)} | {representative} |"
            )
        sections.append(
            ReportSection(
                id="comparison",
                title=labels["comparison"],
                body="\n".join(rows),
                claim_indexes=sorted(set(all_indexes)),
                kind="comparison",
            )
        )

    themes: list[str] = []
    for direction in context.directions:
        for term in direction.top_terms[:2]:
            if term not in themes:
                themes.append(term)
    if themes:
        sections.append(
            ReportSection(
                id="themes",
                title=labels["themes"],
                body=", ".join(themes[:12]),
                kind="themes",
            )
        )

    for insight in insights:
        body, claim_ids = _section_body(insight, index_of, language)
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
                title=labels["gaps"],
                body=(
                    f"{labels['duplicates']}={context.meta.get('duplicates', 0)}; "
                    f"{labels['dropped']}={context.meta.get('dropped_claims', 0)}; "
                    f"{labels['failed']}={len(context.meta.get('failed_papers') or [])}"
                ),
                kind="gaps",
            )
        )

    if cards:
        rows = [f"| {labels['paper']} | {labels['title']} | {labels['claims']} |", "|---|---|---|"]
        by_paper = context.claim_set.by_paper()
        for card in cards:
            rows.append(f"| {card.paper_id} | {card.title[:80]} | {len(by_paper.get(card.paper_id, []))} |")
        sections.append(
            ReportSection(id="index", title=labels["index"], body="\n".join(rows), kind="paper_index")
        )
    return sections


def validate_report(report: Report, *, language: str = "en") -> ValidationResult:
    errors: list[str] = []
    seen_claims: set[int] = set()
    for section in report.sections:
        if section.kind in {"overview", "gaps", "paper_index", "themes"}:
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
    fallback_count: int = 0,
    coverage: float = 0.0,
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
    word_count = _word_count(body)
    thin = len(context.cards) < 5 or len(context.claim_set.claims) < 5 or word_count < 300
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
        fallback_count=fallback_count,
        coverage=coverage,
        thin=thin,
        word_count=word_count,
    )


def build_report_bundle(
    settings: Settings,
    *,
    run_id: str,
    topic_id: str,
    paper_ids: list[str],
    title: str,
    period: str | None = None,
    gateway: Any | None = None,
) -> tuple[Report, ReportContext]:
    language = settings.report.language
    started = time.monotonic()
    context = build_context(settings, paper_ids, gateway=gateway)
    if time.monotonic() - started > settings.report.step_timeout_s:
        logger.warning("report.step_timeout", extra={"step": "context"})
        report = assemble_report(
            run_id=run_id,
            topic_id=topic_id,
            title=title,
            period=period,
            context=context,
            insights=[],
            language=language,
            generated_by="template",
            fallback_count=len(context.directions),
            coverage=0.0,
        )
        report = report.model_copy(update={"fallback_reason": "E_REPORT_TIMEOUT"})
        return report, context
    insights = synthesize_all(
        context.directions,
        context.claim_set.claims,
        gateway=gateway if settings.report.synthesis else None,
        language=language,
        max_tokens=settings.report.max_tokens_synthesis,
    )
    llm_insights = sum(1 for item in insights if item.generated_by == "llm")
    fallback_count = len(insights) - llm_insights if settings.report.synthesis and gateway else 0
    if not settings.report.synthesis or gateway is None:
        generated_by = "template"
    elif fallback_count:
        generated_by = "hybrid"
    else:
        generated_by = "llm"
    by_paper = context.claim_set.by_paper()
    covered = sum(1 for card in context.cards if by_paper.get(card.paper_id))
    coverage = round(covered / len(context.cards), 4) if context.cards else 0.0
    report = assemble_report(
        run_id=run_id,
        topic_id=topic_id,
        title=title,
        period=period,
        context=context,
        insights=insights,
        language=language,
        generated_by=generated_by,
        fallback_count=fallback_count,
        coverage=coverage,
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
            fallback_count=len(insights),
            coverage=0.0,
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
            "fallback_count": report.fallback_count,
            "coverage": report.coverage,
        },
    )
    return report, context


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
    report, _context = build_report_bundle(
        settings,
        run_id=run_id,
        topic_id=topic_id,
        paper_ids=paper_ids,
        title=title,
        period=period,
        gateway=gateway,
    )
    return report
