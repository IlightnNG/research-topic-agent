"""归一化与去单单测（Phase 0 step 5.2 验收：id 优先级 / 缺字段 / 多作者）。"""

from __future__ import annotations

from lit_agent_min.models import Author, Paper
from lit_agent_min.normalize import (
    canonical_id,
    dedup_papers,
    name_norm,
    normalize_doi,
    openalex_work_to_paper,
    reconstruct_abstract,
    similar_title,
)


def _paper(
    paper_id: str, title: str, *, year: int | None = 2026, authors=None, abstract="x"
) -> Paper:
    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        authors=authors or [Author(author_id="A1", name="Ada Lovelace", name_norm="ada lovelace")],
        year=year,
        source="openalex",
    )


# ---- id 优先级（DOI → W → arxiv → 标题指纹） ---- #
def test_canonical_id_prefers_doi() -> None:
    assert (
        canonical_id(doi="https://doi.org/10.1234/ABC", openalex_id="W99", title="t")
        == "10.1234/abc"
    )


def test_canonical_id_falls_back_to_openalex_then_arxiv() -> None:
    assert canonical_id(openalex_id="https://openalex.org/W123") == "W123"
    assert canonical_id(arxiv_id="2401.00001") == "arxiv:2401.00001"


def test_canonical_id_uses_title_fingerprint_when_no_ids() -> None:
    first = canonical_id(title="A Study of Things", year=2026)
    assert first.startswith("title:")
    assert first == canonical_id(title="A Study of Things!", year=2026)  # 标点不影响指纹


def test_normalize_doi_rejects_non_doi() -> None:
    assert normalize_doi("https://example.com/x") is None
    assert normalize_doi(None) is None


def test_name_norm_strips_accents_and_punctuation() -> None:
    assert name_norm("  José  O'Neill-Smith ") == "jose o neill smith"


# ---- 缺字段 ---- #
def test_openalex_work_without_doi_or_abstract_still_normalizes() -> None:
    work = {
        "id": "https://openalex.org/W1",
        "title": "No DOI Paper",
        "publication_year": 2025,
        "authorships": [{"author": {"display_name": "Solo Author"}}],
    }
    paper = openalex_work_to_paper(work)
    assert paper.paper_id == "W1"
    assert paper.abstract == ""
    assert paper.authors[0].author_id.startswith("name:")
    assert paper.year == 2025


def test_openalex_work_missing_year_is_none() -> None:
    paper = openalex_work_to_paper({"id": "https://openalex.org/W2", "title": "T"})
    assert paper.year is None


def test_reconstruct_abstract_orders_words() -> None:
    inverted = {"world": [1], "hello": [0], "again": [2]}
    assert reconstruct_abstract(inverted) == "hello world again"
    assert reconstruct_abstract(None) == ""


# ---- 多作者 ---- #
def test_openalex_work_keeps_all_authors_in_order() -> None:
    work = {
        "id": "https://openalex.org/W3",
        "title": "Multi",
        "authorships": [
            {"author": {"id": "https://openalex.org/A1", "display_name": "First Author"}},
            {"author": {"id": "https://openalex.org/A2", "display_name": "Second Author"}},
            {"author": {"display_name": "Third Author"}},
        ],
    }
    paper = openalex_work_to_paper(work)
    assert [a.name for a in paper.authors] == ["First Author", "Second Author", "Third Author"]
    assert paper.authors[0].author_id == "A1"
    assert paper.authors[2].author_id.startswith("name:")


# ---- 去重（D6 三段式） ---- #
def test_dedup_merges_same_id_records() -> None:
    """同 canonical id 的重复行：去重后只剩一条，但**不计入 version-copy 合并**（语义不同）。"""
    result = dedup_papers([_paper("10.1/x", "Same Title"), _paper("10.1/x", "Same Title")])
    assert len(result.unique) == 1
    assert result.stats["dropped_same_id_rows"] == 1
    assert result.stats["merged_version_copies"] == 0
    assert result.stats["duplicate_rate"] == 0.5


def test_dedup_merges_version_copies_with_different_ids() -> None:
    """同标题 + 同年 + 同首作者，但 id 不同（DOI vs W id）= 典型 version copy。"""
    a = _paper("10.1/x", "Reliable Multi-Agent Orchestration", year=2026)
    b = _paper("W123", "Reliable Multi-Agent Orchestration", year=2026)
    result = dedup_papers([a, b])
    assert len(result.unique) == 1
    assert "W123" in result.merged[result.unique[0].paper_id]


def test_dedup_keeps_different_papers_separate() -> None:
    a = _paper("10.1/a", "Graph Retrieval for Science", year=2026)
    b = _paper("10.1/b", "Vision Language Models on the Edge", year=2026)
    result = dedup_papers([a, b])
    assert len(result.unique) == 2
    assert result.merged == {}


def test_dedup_prefers_record_with_abstract_as_primary() -> None:
    with_abs = _paper("10.1/with", "Same Title Here", abstract="real abstract text")
    without = _paper("W9", "Same Title Here", abstract="")
    result = dedup_papers([without, with_abs])
    assert len(result.unique) == 1
    assert result.unique[0].abstract == "real abstract text"


def test_similar_title_is_bounded() -> None:
    assert similar_title("A Reliable Multi Agent Bus", "A Reliable Multi Agent Bus") == 1.0
    assert 0.0 <= similar_title("alpha beta gamma", "delta epsilon") <= 1.0
    # 归一化后没有 >2 字符的实词时返回 0（短标题/纯符号标题不参与模糊合并）
    assert similar_title("A", "A") == 0.0
    assert similar_title("On It", "On It") == 0.0
