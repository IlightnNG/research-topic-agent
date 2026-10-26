"""报告生成（1.12 D-MIN）：证据卡 → claims → 确定性 Markdown。

三条不可协商的规则
1. 每条 claim **必带 citation**；无法落地的内容**保留为 `unsupported`**（丢弃会伪造 grounding）；
2. 渲染**确定性**：同输入两次输出逐字节一致（否则 D4 幂等失效）；
3. `content_sha` 由正文算出，作为 `reports` 表的幂等键。
"""

from __future__ import annotations

import hashlib
from typing import Any

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, EvidenceCard, Support
from lit_agent.models.report import Report

__all__ = ["build_report", "render_markdown"]


def render_markdown(cards: list[EvidenceCard], *, title: str) -> str:
    """确定性渲染：按 `paper_id` 排序，标题 + 每条证据一段（含年份/venue/片段）。"""
    lines = [f"# {title}", "", f"{len(cards)} evidence items.", ""]
    for card in sorted(cards, key=lambda item: (item.paper_id, item.snippet)):
        year = card.year if card.year is not None else "n.d."
        lines.append(f"- **{card.title}** ({year}, {card.source})")
        lines.append(f"  > {card.snippet}")
    return "\n".join(lines).rstrip() + "\n"


def build_report(
    cards: list[EvidenceCard],
    *,
    topic_id: str,
    run_id: str,
    title: str = "Weekly research report",
    report_id: str | None = None,
) -> Report:
    """把证据卡折成报告 + claims（一卡一 claim，全部带引用）。"""
    content_md = render_markdown(cards, title=title)
    digest = hashlib.sha256(content_md.encode("utf-8")).hexdigest()[:12]

    claims: list[Claim] = []
    for card in sorted(cards, key=lambda item: (item.paper_id, item.snippet)):
        claims.append(
            Claim(
                text=f"{card.title} ({card.year or 'n.d.'}) — {card.snippet}",
                citations=[Citation(paper_id=card.paper_id, snippet=card.snippet)],
                support=Support.SUPPORTED,
            )
        )
    if not claims:
        # 空证据也必须给出可解释产物，而不是"看起来成功但没内容"
        claims.append(
            Claim(text="No citable evidence was found in this run.", citations=[], support=Support.UNSUPPORTED)
        )

    return Report(
        report_id=report_id or f"{run_id}:{digest}",
        topic_id=topic_id,
        run_id=run_id,
        title=title,
        content_md=content_md,
        content_sha=digest,
        claims=claims,
        n_claims=len(claims),
    )


def build_report_from_claims(
    claims: list[Claim],
    *,
    topic_id: str,
    run_id: str,
    title: str = "Weekly research report",
) -> Report:
    """由**已有 claims** 生成报告（不再二次取证据卡，避免"两处各自取数"）。"""
    digest_source = "\n".join(claim.text for claim in claims) or f"empty:{run_id}"
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    if claims:
        lines = [f"# {title}", "", f"{len(claims)} findings (each with citations).", ""]
        for claim in claims:
            refs = ", ".join(citation.paper_id for citation in claim.citations) or "(no citation)"
            lines.append(f"- {claim.text}  \n  refs: {refs}")
        content_md = "\n".join(lines) + "\n"
    else:
        content_md = f"# {title}\n\nNo citable evidence was found in this run.\n"
    return Report(
        sections=build_sections(claims),
        report_id=f"{run_id}:{digest}",
        topic_id=topic_id,
        run_id=run_id,
        title=title,
        content_md=content_md,
        content_sha=digest,
        claims=claims or [Claim(text="No citable evidence was found in this run.", citations=[], support=Support.UNSUPPORTED)],
        n_claims=len(claims) if claims else 1,
    )


def build_sections(claims: list[Claim], *, per_section: int = 5) -> list[Any]:
    """把 claims 分成若干"节"（S12）：报告按节渲染，不再依赖 API 派生。"""
    from lit_agent.models.report import ReportSection

    if not claims:
        return []
    sections: list[Any] = []
    for start in range(0, len(claims), per_section):
        block = claims[start : start + per_section]
        body = "\n".join(f"- {claim.text}" for claim in block)
        sections.append(
            ReportSection(
                id=f"S{len(sections) + 1}",
                title=f"Findings {len(sections) + 1}",
                body=body,
                claim_indexes=list(range(start, start + len(block))),
            )
        )
    return sections
