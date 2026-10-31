"""3.5 / S4-S6: tiered evidence, vector directions, comparison matrix."""

from __future__ import annotations

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, Support
from lit_agent.report.assemble import assemble_report
from lit_agent.report.cards import PaperCard
from lit_agent.report.claims import ClaimSet
from lit_agent.report.clusters import Direction
from lit_agent.report.context import ReportContext
from lit_agent.report.embeddings import build_directions_embedding
from lit_agent.report.evidence import select_evidence_tiers
from lit_agent.report.synthesis import DirectionInsight, InsightItem


def _card(index: int, text: str = "tool use agents reliability") -> PaperCard:
    return PaperCard(
        paper_id=f"P{index}",
        title=f"Paper {index} on {text}",
        abstract=f"{text} study {index}",
        claims=[{"text": text, "quote": text}],
    )


def _claim(index: int) -> Claim:
    return Claim(
        text=f"tool use improves reliability {index}",
        citations=[Citation(paper_id=f"P{index}", snippet="tool use improves reliability")],
        support=Support.SUPPORTED,
        claim_id=f"P{index}-C1",
    )


def test_tiered_evidence() -> None:
    cards = [_card(index) for index in range(10)]
    claims = [_claim(index) for index in range(10)]
    context = ReportContext(cards=cards, claim_set=ClaimSet(claims=claims))
    tiers = select_evidence_tiers(context, deep_ratio=0.3, min_deep=3)
    assert len(tiers.l1_paper_ids) == 10
    assert len(tiers.deep_paper_ids) == 3
    assert tiers.ratio == 0.3
    assert set(tiers.quote_paper_ids) <= set(tiers.deep_paper_ids)


def test_embedding_directions_are_stable() -> None:
    cards = [_card(index) for index in range(6)]
    claims = [_claim(index) for index in range(6)]
    first = build_directions_embedding(cards, claims, min_size=2, max_clusters=4, threshold=0.3)
    second = build_directions_embedding(
        list(reversed(cards)), claims, min_size=2, max_clusters=4, threshold=0.3
    )
    assert [item.paper_ids for item in first] == [item.paper_ids for item in second]
    assert first


def test_report_has_comparison_and_themes() -> None:
    cards = [_card(index) for index in range(4)]
    claims = [_claim(index) for index in range(4)]
    direction = Direction(
        id="D1",
        name="Tool use",
        paper_ids=[f"P{index}" for index in range(4)],
        claim_ids=[f"P{index}-C1" for index in range(4)],
        top_terms=["tool", "reliability"],
    )
    context = ReportContext(
        cards=cards,
        claim_set=ClaimSet(claims=claims),
        directions=[direction],
    )
    insight = DirectionInsight(
        direction_id="D1",
        name="Tool use",
        definition="Tool-using agents.",
        common_ground=[InsightItem(text="shared", claim_ids=[f"P{index}-C1" for index in range(4)])],
        generated_by="template",
    )
    report = assemble_report(
        run_id="r1",
        topic_id="t",
        title="Research",
        period=None,
        context=context,
        insights=[insight],
        language="en",
        generated_by="template",
    )
    kinds = [section.kind for section in report.sections]
    assert "comparison" in kinds
    assert "themes" in kinds
    comparison = next(section for section in report.sections if section.kind == "comparison")
    assert "| Direction |" in comparison.body
    assert comparison.claim_indexes
