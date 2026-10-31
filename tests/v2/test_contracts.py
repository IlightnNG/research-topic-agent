"""Contract round-trip and boundary tests."""

from __future__ import annotations

import json

from lit_agent_v2.contracts.events import EventEnvelope
from lit_agent_v2.contracts.report import (
    Claim,
    Direction,
    EvidenceArtifact,
    MapArtifact,
    Paper,
    ReportDraft,
    Section,
    SourceArtifact,
)


def test_source_artifact_roundtrip() -> None:
    source = SourceArtifact(topic_id="t", query="q", papers=[Paper("P1", "Title")])
    payload = source.to_dict()
    assert payload["schema_version"] == 1
    assert SourceArtifact.from_dict(payload).papers[0].paper_id == "P1"


def test_evidence_and_map_roundtrip() -> None:
    evidence = EvidenceArtifact(
        papers=[{"paper_id": "P1", "claims": [{"claim_id": "P1-C1"}]}],
        with_claims=1,
        fulltext=1,
        claims=1,
        research_claims=1,
        quote_checks=1,
        quote_ok=1,
    )
    assert EvidenceArtifact.from_dict(evidence.to_dict()).claim_purity == 1.0
    mapping = MapArtifact(
        directions=[Direction("D1", "Topic", ["P1"])],
        papers=1,
        count_quality="complete",
    )
    restored = MapArtifact.from_dict(mapping.to_dict())
    assert restored.directions[0].paper_ids == ["P1"]
    assert restored.min_size == 1


def test_report_draft_roundtrip() -> None:
    draft = ReportDraft(
        title="T",
        content_md="body",
        content_sha="sha",
        sections=[Section("overview", "overview", "Overview", "body", [0])],
        word_count=1,
        claims=[Claim("P1-C1", "P1", "finding", "quote").to_dict()],
    )
    restored = ReportDraft.from_dict(json.loads(json.dumps(draft.to_dict())))
    assert restored.sections[0].claim_indexes == [0]
    assert restored.state == "complete"


def test_event_envelope_shape() -> None:
    event = EventEnvelope(
        event_id="e1",
        run_id="r1",
        seq=1,
        ts="2026-10-31T00:00:00Z",
        type="node.finished",
        module="M4",
        node_id="write",
    )
    payload = event.to_dict()
    assert payload["module"] == "M4"
    assert payload["schema_version"] == 1
