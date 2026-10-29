"""3.2 / S3–S4：claims 规范化 + 方向聚类 + context 装配。"""

from __future__ import annotations

from pathlib import Path

from lit_agent.models.evidence import Support
from lit_agent.report.cards import PaperCard
from lit_agent.report.claims import build_claims, is_research_claim
from lit_agent.report.clusters import build_directions, label_directions
from lit_agent.report.context import build_context


def card(paper_id: str, title: str, text: str, claims: list[str] | None = None) -> PaperCard:
    values = claims or [text]
    return PaperCard(
        paper_id=paper_id,
        title=title,
        abstract=text,
        claims=[{"text": item, "quote": item} for item in values],
    )


def test_claim_ids_are_stable_and_cited() -> None:
    cards = [card("P1", "Tool use", "tool use improves success", ["tool use improves success"])]
    claim_set = build_claims(cards, max_per_paper=3)

    assert len(claim_set.claims) == 1
    claim = claim_set.claims[0]
    assert claim.claim_id == "P1-C1"
    assert claim.text_sha
    assert claim.citations[0].paper_id == "P1"
    assert claim.support == Support.SUPPORTED


def test_claims_dedupe_across_papers() -> None:
    text = "tool use improves task success"
    cards = [card("P1", "A", text), card("P2", "B", text)]
    claim_set = build_claims(cards)

    assert len(claim_set.claims) == 1
    assert claim_set.duplicates == 1


def test_claims_respect_per_paper_limit() -> None:
    cards = [card("P1", "A", "tool use", ["first finding improves accuracy", "second finding improves speed", "third finding reduces cost", "fourth finding improves recall"])]
    claim_set = build_claims(cards, max_per_paper=2)
    assert len(claim_set.claims) == 2
    assert [claim.claim_id for claim in claim_set.claims] == ["P1-C1", "P1-C2"]


def test_cluster_groups_similar_papers() -> None:
    cards = [
        card("P1", "Tool use agents", "tool use improves agent success"),
        card("P2", "Agents with tools", "tool use improves agent reliability"),
        card("P3", "Protein folding", "cryo electron microscopy of proteins"),
    ]
    claims = build_claims(cards).claims
    directions = build_directions(cards, claims, min_size=2, max_clusters=6)

    groups = {frozenset(direction.paper_ids) for direction in directions}
    assert frozenset({"P1", "P2"}) in groups
    assert any("P3" in direction.paper_ids for direction in directions)


def test_cluster_is_deterministic() -> None:
    cards = [card("P2", "Tool use", "tool use improves success"), card("P1", "Agents", "tool use improves agents")]
    claims = build_claims(cards).claims
    first = build_directions(cards, claims)
    second = build_directions(list(reversed(cards)), claims)

    assert [(d.id, d.paper_ids) for d in first] == [(d.id, d.paper_ids) for d in second]


def test_cluster_empty_is_safe() -> None:
    assert build_directions([], []) == []


def test_label_fallback_on_llm_error() -> None:
    cards = [card("P1", "Tool", "tool use"), card("P2", "Agents", "tool use agents")]
    claims = build_claims(cards).claims
    directions = build_directions(cards, claims)

    class Broken:
        def chat_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("down")

    before = directions[0].name
    label_directions(directions, cards, gateway=Broken())
    assert directions[0].name == before


def test_build_context_uses_cache(tmp_path: Path) -> None:
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=2)
    context = build_context(settings, ["P0", "P1"])

    assert len(context.cards) == 2
    assert context.claim_set.claims
    assert context.directions
    assert context.meta["papers"] == 2


def test_build_context_survives_bad_paper(tmp_path: Path) -> None:
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=1)
    context = build_context(settings, ["P0", "missing"])

    assert len(context.cards) == 1
    assert context.meta["failed_papers"] == ["missing"]
    assert settings.report.enabled is True


def test_bibliographic_claims_are_filtered() -> None:
    assert not is_research_claim("The work was published at ACL 2024.")
    assert not is_research_claim("Proceedings of the 62nd Annual Meeting.")
    assert not is_research_claim("Ada Lovelace, Alan Turing, Grace Hopper")
    assert is_research_claim("Tool use improves task success and reliability.")

    cards = [
        card(
            "P1",
            "A",
            "tool use improves success",
            ["published at ACL 2024", "tool use improves task success"],
        )
    ]
    claim_set = build_claims(cards)
    assert len(claim_set.claims) == 1
    assert claim_set.filtered == 1


def test_direction_names_exclude_venue_terms() -> None:
    from lit_agent.report.clusters import build_directions

    cards = [
        card("P1", "ACL 2024 paper", "tool use improves agents"),
        card("P2", "ACL 2024 paper", "tool use improves reliability"),
    ]
    directions = build_directions(cards, build_claims(cards).claims)
    assert all("ACL" not in direction.name for direction in directions)
