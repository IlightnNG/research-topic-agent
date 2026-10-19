"""Step 1.6/1.7 单元验收：归一化映射、白名单口径、分块预算。"""

from __future__ import annotations

from lit_agent.parsing.chunking import chunk_text, count_tokens, tokenizer_name
from lit_agent.parsing.pdf import extract_pdf_text
from lit_agent.sources.arxiv import paper_from_entry
from lit_agent.sources.normalize import (
    canonical_id,
    name_norm,
    openalex_work_to_paper,
    reconstruct_abstract,
)
from lit_agent.sources.whitelist import is_whitelisted, selector_key


def work(**overrides: object) -> dict:
    base = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1000/ABC",
        "title": "  LLM Agents for Tool Use  ",
        "publication_year": 2024,
        "publication_date": "2024-05-01",
        "updated_date": "2024-06-01T00:00:00Z",
        "language": "en",
        "cited_by_count": 12,
        "open_access": {"is_oa": True},
        "primary_location": {
            "source": {"id": "https://openalex.org/S42", "display_name": "NeurIPS"}
        },
        "best_oa_location": {"pdf_url": "https://example.org/p.pdf"},
        "referenced_works": ["https://openalex.org/W111", "https://openalex.org/W222"],
        "authorships": [
            {"author": {"id": "https://openalex.org/A1", "display_name": "Ada Lovelace"}}
        ],
        "abstract_inverted_index": {"agents": [0], "plan": [1]},
    }
    base.update(overrides)
    return base


def test_canonical_id_priority() -> None:
    assert canonical_id(doi="https://doi.org/10.1/X", openalex_id="W1") == "10.1/x"
    assert canonical_id(openalex_id="https://openalex.org/W9") == "W9"
    assert canonical_id(arxiv_id="2401.00001") == "arxiv:2401.00001"
    assert canonical_id(title="Some Title", year=2024).startswith("title:")


def test_name_norm_and_abstract() -> None:
    assert name_norm("  Ada  Lovelace ") == "ada lovelace"
    assert reconstruct_abstract({"b": [1], "a": [0]}) == "a b"


def test_openalex_work_maps_contract_fields() -> None:
    paper = openalex_work_to_paper(work())

    assert paper.paper_id == "10.1000/abc"
    assert paper.title == "LLM Agents for Tool Use"
    assert paper.source_id == "W123"
    assert paper.venue_id == "S42"
    assert paper.venue == "NeurIPS"
    assert paper.is_oa is True
    assert paper.language == "en"
    assert paper.cited_by_count == 12
    assert paper.references == ["W111", "W222"]
    assert paper.oa_pdf_url == "https://example.org/p.pdf"
    assert paper.abstract == "agents plan"


def test_whitelist_is_by_source_id() -> None:
    # 按 id 命中
    assert is_whitelisted(work(), ["S42"]) is True
    # 名称相同但 id 不同 → 不命中（Phase 0 的教训）
    renamed = work(primary_location={"source": {"id": "S99", "display_name": "NeurIPS"}})
    assert is_whitelisted(renamed, ["S42"]) is False
    assert is_whitelisted(work(), []) is False


def test_selector_key_is_order_insensitive() -> None:
    a = selector_key({"venue_ids": ["V1"], "from_year": 2023, "type": "article"})
    b = selector_key({"type": "article", "from_year": 2023, "venue_ids": ["V1"]})
    assert a == b
    assert a != selector_key({"venue_ids": ["V2"], "from_year": 2023, "type": "article"})


def test_chunking_respects_budget() -> None:
    text = (
        ". ".join(f"Sentence number {index} about llm agents and tools" for index in range(60))
        + "."
    )
    pieces = chunk_text(text, budget_tokens=120, overlap_tokens=10)

    assert pieces
    assert all(piece.tokens <= 120 for piece in pieces)
    # 除最后一块外，利用率应接近预算（±10% 口径）
    for piece in pieces[:-1]:
        assert piece.tokens >= 0.85 * 120
    assert [piece.index for piece in pieces] == list(range(len(pieces)))


def test_chunking_handles_empty_and_long_sentence() -> None:
    assert chunk_text("") == []
    long_sentence = " ".join(["word"] * 400)
    pieces = chunk_text(long_sentence, budget_tokens=50)
    assert len(pieces) > 1
    assert all(piece.tokens <= 60 for piece in pieces)


def test_tokenizer_is_deterministic() -> None:
    text = "LLM agents use tools."
    assert count_tokens(text) == count_tokens(text)
    assert count_tokens("") == 0
    assert tokenizer_name().startswith(("tiktoken", "heuristic"))


def test_missing_pdf_returns_error_not_exception(tmp_path) -> None:
    result = extract_pdf_text(tmp_path / "nope.pdf")
    assert result.ok is False
    assert "不存在" in (result.error or "")


def test_arxiv_entry_mapping() -> None:
    class FakeAuthor:
        name = "Ada Lovelace"

    class FakeEntry:
        entry_id = "http://arxiv.org/abs/2401.00001v1"
        title = "A  Paper  Title"
        summary = "short abstract"
        authors = [FakeAuthor()]
        published = None
        updated = None
        pdf_url = "http://arxiv.org/pdf/2401.00001v1"

    paper = paper_from_entry(FakeEntry())
    assert paper.paper_id == "arxiv:2401.00001v1"
    assert paper.title == "A Paper Title"
    assert paper.source == "arxiv"
    assert paper.is_oa is True
    assert paper.authors[0].name_norm == "ada lovelace"
