"""报告生成（1.12 D-MIN）：证据卡 → claims → 确定性 Markdown。

三条不可协商的规则
1. 每条 claim **必带 citation**；无法落地的内容**保留为 `unsupported`**（丢弃会伪造 grounding）；
2. 渲染**确定性**：同输入两次输出逐字节一致（否则 D4 幂等失效）；
3. `content_sha` 由正文算出，作为 `reports` 表的幂等键。
"""

from __future__ import annotations

import hashlib

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, EvidenceCard, Support
from lit_agent.models.report import Report

__all__ = ["build_report", "render_markdown"]


def render_markdown(cards: list[EvidenceCard], *, title: str) -> str:
    """确定性渲染：按 `paper_id` 排序，标题 + 每条证据一段（含年份/venue/片段）。"""
    lines = [f"# {title}", "", f"共 {len(cards)} 条证据。", ""]
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
            Claim(text="本轮未检索到可引用证据", citations=[], support=Support.UNSUPPORTED)
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
