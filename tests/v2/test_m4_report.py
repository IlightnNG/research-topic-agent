"""M4-P01: direction quality, count reconciliation, paper index."""

from __future__ import annotations

from lit_agent_v2.contracts.report import Direction, EvidenceArtifact, MapArtifact
from lit_agent_v2.domains.report.map import MapService
from lit_agent_v2.domains.report.policy import policy_for
from lit_agent_v2.domains.report.write import WriteService

VOCAB = [
    "Tool routing improves agent success on benchmark tasks.",
    "Dense retrieval improves passage ranking quality on benchmarks.",
    "Hierarchical planning improves task decomposition for long horizon agents.",
    "Episodic memory improves context retention across conversation turns.",
    "Rubric evaluation improves scoring agreement with human annotators.",
]


def _evidence(count: int = 50, groups: int = 5) -> EvidenceArtifact:
    evidence = EvidenceArtifact(fulltext=count)
    for index in range(count):
        group = index % groups
        claim_id = f"P{index}-C1"
        text = f"{VOCAB[group]} Study {index} reports this result."
        evidence.papers.append(
            {
                "paper_id": f"P{index}",
                "title": f"Study {index}",
                "abstract": text,
                "authors": [f"Author {group}"],
                "venue": "ACL",
                "year": 2025,
                "url": f"https://example.org/{index}",
                "level": "L2",
                "fulltext_available": True,
                "claims": [
                    {
                        "claim_id": claim_id,
                        "paper_id": f"P{index}",
                        "text": text,
                        "quote": text,
                        "claim_type": "finding",
                    }
                ],
            }
        )
        evidence.claims += 1
        evidence.research_claims += 1
        evidence.quote_checks += 1
        evidence.quote_ok += 1
        evidence.with_claims += 1
    return evidence


def test_directions_and_names_are_safe() -> None:
    mapping = MapService().build(_evidence())
    assert 5 <= len(mapping.directions) <= 8
    assert mapping.count_quality == "complete"
    assert min(len(item.paper_ids) for item in mapping.directions) >= 3
    assert max(len(item.paper_ids) for item in mapping.directions) / mapping.papers <= 0.6
    names = " ".join(item.name for item in mapping.directions).lower()
    assert "author" not in names
    assert "acl" not in names


def test_report_counts_and_index_metadata() -> None:
    evidence = _evidence()
    mapping = MapService().build(evidence)
    draft = WriteService().build(
        run_id="r1",
        topic_id="t",
        title="Report",
        evidence=evidence,
        mapping=mapping,
    )
    assert len(draft.claims) == 50
    assert "50 verified claims" in draft.sections[0].body
    deep = [section for section in draft.sections if section.kind == "deep_dive"]
    displayed = [idx for section in deep for idx in section.claim_indexes]
    assert len(displayed) == 50
    assert len(set(displayed)) == 50
    ledger = next(section for section in draft.sections if section.kind == "claim_ledger")
    assert len(ledger.claim_indexes) == 50
    matrix = next(section for section in draft.sections if section.kind == "comparison")
    rows = [line for line in matrix.body.splitlines() if len(line.split("|")) == 6 and line.split("|")[3].strip().isdigit()]
    assert sum(int(line.split("|")[3].strip()) for line in rows) == 50
    index = next(section for section in draft.sections if section.kind == "paper_index")
    assert "| Authors |" in index.body
    assert "Author 0" in index.body
    assert "ACL" in index.body
    assert "https://example.org/0" in index.body
    assert draft.word_count >= policy_for(50).min_words


def test_degraded_for_collapsed_direction() -> None:
    evidence = _evidence()
    mapping = MapArtifact(
        directions=[Direction("D1", "Everything", [paper["paper_id"] for paper in evidence.papers])],
        papers=len(evidence.papers),
        count_quality="deficit",
    )
    draft = WriteService().build(
        run_id="r1", topic_id="t", title="Report", evidence=evidence, mapping=mapping
    )
    assert draft.state == "degraded"


def test_claims_are_all_in_body_not_just_ledger() -> None:
    evidence = _evidence()
    mapping = MapService().build(evidence)
    draft = WriteService().build(
        run_id="r1", topic_id="t", title="Report", evidence=evidence, mapping=mapping
    )
    for index in range(50):
        assert f"[C{index + 1}]" in draft.content_md


def test_policy_scales_with_corpus() -> None:
    small = policy_for(20, 20)
    medium = policy_for(50, 50)
    large = policy_for(100, 100)
    assert small.target_directions < medium.target_directions < large.target_directions
    assert small.target_words < medium.target_words < large.target_words
    assert small.max_direction_share >= large.max_direction_share
    assert small.min_direction_size <= large.min_direction_size
