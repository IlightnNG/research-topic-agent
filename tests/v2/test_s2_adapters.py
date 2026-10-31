"""V2 S2 adapters: OpenAlex, PDF, LLM claims, ingest."""

from __future__ import annotations

from pathlib import Path

import httpx
import pymupdf

from lit_agent_v2.domains.report.claim_extractor import LLMClaimExtractor, extract_deterministic
from lit_agent_v2.domains.report.contracts import Paper
from lit_agent_v2.domains.report.ingest import IngestService, LocalCorpus
from lit_agent_v2.domains.report.openalex import OpenAlexAdapter
from lit_agent_v2.domains.report.pdf import extract_pdf_text


def test_openalex_adapter_maps_records() -> None:
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Tool use",
                "doi": "https://doi.org/10.1/x",
                "publication_year": 2025,
                "abstract_inverted_index": {"Tool": [0], "use": [1], "works": [2]},
                "primary_location": {"source": {"display_name": "ACL"}},
                "best_oa_location": {"pdf_url": "https://example.org/p.pdf"},
            }
        ]
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = httpx.Client(transport=transport)
    papers = OpenAlexAdapter(client=client).fetch("tool use", limit=10)
    assert papers[0].paper_id == "W1"
    assert papers[0].abstract == "Tool use works"
    assert papers[0].venue == "ACL"
    assert papers[0].pdf_url.endswith("p.pdf")


def test_pdf_text_extraction() -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Tool use improves task success.")
    data = document.tobytes()
    document.close()
    text = extract_pdf_text(data)
    assert "Tool use improves task success." in text


def test_llm_claim_extractor_filters_non_verbatim() -> None:
    class Client:
        def chat_json(self, messages, **kwargs):  # noqa: ANN001
            return {
                "claims": [
                    {"text": "tool use helps", "quote": "Tool use helps."},
                    {"text": "not in source", "quote": "nope"},
                ]
            }, None

    claims = LLMClaimExtractor(Client())( "P1", "Tool use helps. Agents solve tasks.")
    assert len(claims) == 1
    assert claims[0].quote == "Tool use helps."


def test_deterministic_extractor_rejects_bibliographic() -> None:
    claims = extract_deterministic("P1", "Published at ACL 2024. Tool use improves success.")
    assert len(claims) == 1
    assert claims[0].quote == "Tool use improves success."


def test_ingest_service_writes_corpus(tmp_path: Path) -> None:
    class Adapter:
        def fetch(self, query, **kwargs):  # noqa: ANN001
            return [Paper(paper_id="P1", title="Tool use", abstract="Tool use helps.")]

    corpus = IngestService(Adapter(), tmp_path / "corpus").ingest("tool", limit=10)
    assert isinstance(corpus, LocalCorpus)
    assert corpus.papers()[0].paper_id == "P1"
    assert (tmp_path / "corpus" / "papers.jsonl").exists()
