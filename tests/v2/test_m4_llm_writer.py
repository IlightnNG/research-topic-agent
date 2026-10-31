"""M4-P02: modular LLM writer, schema gate, fallback."""

from __future__ import annotations

import json
import os

import pytest

from lit_agent_v2.contracts.report import EvidenceArtifact
from lit_agent_v2.domains.report.audit import audit_report
from lit_agent_v2.domains.report.llm_writer import LLMReportWriter
from lit_agent_v2.domains.report.map import MapService


def _evidence(count: int = 20, groups: int = 4) -> EvidenceArtifact:
    vocab = [
        "Tool routing improves agent success on benchmark tasks.",
        "Dense retrieval improves passage ranking quality on benchmarks.",
        "Hierarchical planning improves task decomposition for agents.",
        "Episodic memory improves context retention across turns.",
    ]
    evidence = EvidenceArtifact(fulltext=count)
    for index in range(count):
        group = index % groups
        text = f"{vocab[group]} Study {index} reports this result."
        evidence.papers.append(
            {
                "paper_id": f"P{index}",
                "title": f"Study {index}",
                "abstract": text,
                "authors": [f"Author {group}"],
                "venue": "ACL",
                "year": 2025,
                "url": f"https://example.org/{index}",
                "claims": [
                    {
                        "claim_id": f"P{index}-C1",
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
        evidence.with_claims += 1
        evidence.quote_checks += 1
        evidence.quote_ok += 1
    return evidence


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        if self.fail:
            raise RuntimeError("llm down")
        system = messages[0]["content"]
        user = messages[1]["content"]
        if "research report section" in system:
            data = json.loads(user)
            self.calls.append("section")
            body = "### Common ground\n" + "\n".join(
                f"- {item['text']} [{item['ref']}]" for item in data["claims"]
            )
            return {"body": body}, None
        if "overview" in system:
            self.calls.append("overview")
            return {"body": "This report covers the supplied evidence."}, None
        self.calls.append("comparison")
        return {"body": "The directions differ in task and method."}, None


def test_llm_writer_sections_and_counts() -> None:
    evidence = _evidence()
    mapping = MapService().build(evidence)
    writer = LLMReportWriter(FakeClient())
    draft = writer.build(
        run_id="r1", topic_id="t", title="Report", evidence=evidence, mapping=mapping
    )
    assert [section.kind for section in draft.sections].count("deep_dive") >= 3
    assert all(section.claim_indexes for section in draft.sections if section.kind == "deep_dive")
    assert len(draft.claims) == 20
    assert "This report covers" in draft.sections[0].body
    audit = audit_report(draft)
    assert audit.citation_coverage >= 1.0
    assert audit.duplicate_claim_rate == 0.0


def test_llm_failure_falls_back_and_degrades() -> None:
    evidence = _evidence()
    mapping = MapService().build(evidence)
    writer = LLMReportWriter(FakeClient(fail=True), max_attempts=1)
    draft = writer.build(
        run_id="r1", topic_id="t", title="Report", evidence=evidence, mapping=mapping
    )
    assert draft.state == "degraded"
    assert len(draft.claims) == 20
    assert [section.kind for section in draft.sections].count("deep_dive") >= 3


@pytest.mark.skipif(os.environ.get("LIT_V2_LIVE") != "1", reason="set LIT_V2_LIVE=1 for live LLM")
def test_live_llm_report_writer() -> None:
    from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config

    class Counting:
        def __init__(self):
            self.inner = DeepSeekChatClient(load_llm_config())
            self.calls = 0

        def chat_json(self, messages, **kwargs):  # noqa: ANN001
            self.calls += 1
            return self.inner.chat_json(messages, **kwargs)

    client = Counting()
    evidence = _evidence()
    mapping = MapService().build(evidence)
    draft = LLMReportWriter(client, max_attempts=1).build(
        run_id="r1", topic_id="t", title="Report", evidence=evidence, mapping=mapping
    )
    assert client.calls >= 1
    assert len(draft.claims) == 20
    assert [section.kind for section in draft.sections].count("deep_dive") >= 3
