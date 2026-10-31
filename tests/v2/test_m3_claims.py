"""M3-P01: claim types, filters, purity."""

from __future__ import annotations

import os

import pytest

from lit_agent_v2.contracts.report import Paper, SourceArtifact
from lit_agent_v2.domains.report.claim_extractor import (
    LLMClaimExtractor,
    build_claim,
    classify_claim,
    extract_deterministic,
)
from lit_agent_v2.domains.report.evidence import EvidenceService


def test_valid_claims_get_types() -> None:
    text = (
        "We find that tool use improves agent success. "
        "Our framework introduces a new benchmark for evaluation. "
        "However, agents fail under distribution shift on unseen tasks."
    )
    claims = extract_deterministic("P1", text, limit=3)
    assert len(claims) == 3
    assert [claim.claim_type for claim in claims] == ["finding", "method", "limitation"]
    assert all(claim.quote in text for claim in claims)


def test_author_list_rejected() -> None:
    text = "Tongxin Yuan, Zhiwei He, Lingzhong Dong."
    assert build_claim("P1", text, source=text) is None
    assert extract_deterministic("P1", text) == []


def test_references_ack_and_truncated_rejected() -> None:
    samples = [
        "In Proceedings of ACL 2024, we propose a new method.",
        "We thank the reviewers for their helpful comments.",
        "Tool use improves agent success as",
        'Our framework achieves strong results with "unclosed quote.',
    ]
    for sample in samples:
        assert build_claim("P1", sample, source=sample) is None


def test_background_is_not_research() -> None:
    text = "Large language models have recently become popular."
    assert classify_claim(text) == "background"
    assert build_claim("P1", text, source=text) is None


def test_llm_extractor_filters_non_verbatim_and_author() -> None:
    class Client:
        def chat_json(self, messages, **kwargs):  # noqa: ANN001
            return {
                "claims": [
                    {
                        "text": "tool use helps",
                        "quote": "We find that tool use improves agent success.",
                        "type": "finding",
                    },
                    {
                        "text": "author",
                        "quote": "Tongxin Yuan, Zhiwei He.",
                        "type": "finding",
                    },
                ]
            }, None

    text = "We find that tool use improves agent success. Tongxin Yuan, Zhiwei He."
    claims = LLMClaimExtractor(Client())( "P1", text)
    assert len(claims) == 1
    assert claims[0].claim_type == "finding"


def test_evidence_purity_counts_research_only() -> None:
    good = "We find that tool use improves agent success."
    bad = "Tongxin Yuan, Zhiwei He, Lingzhong Dong."
    source = SourceArtifact(
        topic_id="t",
        query="q",
        papers=[Paper(paper_id="P1", title="T", abstract=f"{good} {bad}")],
    )
    evidence = EvidenceService().build(source)
    assert evidence.claims == 1
    assert evidence.research_claims == 1
    assert evidence.claim_purity == 1.0
    assert evidence.papers[0]["claims"][0]["claim_type"] == "finding"


@pytest.mark.skipif(os.environ.get("LIT_V2_LIVE") != "1", reason="set LIT_V2_LIVE=1 for live LLM")
def test_live_llm_claim_extraction() -> None:
    from lit_agent_v2.domains.report.claim_extractor import LLMClaimExtractor
    from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config

    text = (
        "Large language models have become popular. "
        "We find that tool use improves agent success on complex tasks. "
        "Tongxin Yuan, Zhiwei He."
    )
    claims = LLMClaimExtractor(DeepSeekChatClient(load_llm_config()))("P1", text)
    assert claims
    assert all(claim.quote in text for claim in claims)
    assert all(claim.claim_type in {"finding", "method", "dataset", "limitation"} for claim in claims)
