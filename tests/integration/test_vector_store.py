"""Qdrant local 向量库（Step 1.5）：契约 payload、幂等、过滤、身份校验。

一律注入 `HashingEmbedder`：不下载 2.27 GB 模型，也不把"哈希向量"当语义结论。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.session import upgrade_database, write_store_identity
from lit_agent.errors import E_VECTOR_DIM_MISMATCH, E_VECTOR_MODEL_MISMATCH, LitError
from lit_agent.stores.vector import HashingEmbedder, VectorStore, close_clients, paper_text

CONTRACT_PAYLOAD_KEYS = {
    "paper_id",
    "title",
    "year",
    "source",
    "topic_ids",
    "published_at",
    "discovered_at",
}


def settings_for(tmp_path: Path) -> Settings:
    """建库（store_meta 需要 SQLite 已迁移）。"""
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    return settings


def rows() -> list[dict]:
    return [
        {
            "paper_id": "W1",
            "title": "LLM agents survey",
            "abstract": "planning and tools",
            "year": 2024,
            "source": "openalex",
            "published_at": "2024-01-01",
            "discovered_at": "d",
        },
        {
            "paper_id": "W2",
            "title": "Wireless MIMO",
            "abstract": "network optimization",
            "year": 2023,
            "source": "openalex",
            "published_at": "2023-01-01",
            "discovered_at": "d",
        },
        {
            "paper_id": "W3",
            "title": "EDA flow",
            "abstract": "circuit design",
            "year": 2025,
            "source": "arxiv",
            "published_at": "2025-01-01",
            "discovered_at": "d",
        },
    ]


@pytest.fixture(autouse=True)
def _close_clients() -> None:
    yield
    close_clients()


def test_upsert_is_idempotent_and_payload_matches_contract(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = VectorStore.open(settings, HashingEmbedder())
    store.upsert_papers(rows(), topic_ids=["ai-agents"])
    store.upsert_papers(rows(), topic_ids=["ai-agents"])

    assert store.count() == 3
    hits = store.search("LLM agents survey", limit=1)
    assert hits
    assert set(hits[0]["payload"]) == CONTRACT_PAYLOAD_KEYS
    assert hits[0]["payload"]["topic_ids"] == ["ai-agents"]


def test_search_filter_by_year(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = VectorStore.open(settings, HashingEmbedder())
    store.upsert_papers(rows())

    hits = store.search("anything", limit=10, year_from=2024)
    assert {hit["payload"]["year"] for hit in hits} <= {2024, 2025}
    assert len(hits) == 2


def test_search_filter_by_paper_ids(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = VectorStore.open(settings, HashingEmbedder())
    store.upsert_papers(rows())

    hits = store.search("x", limit=10, paper_ids=["W2"])
    assert [hit["paper_id"] for hit in hits] == ["W2"]


def test_model_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    VectorStore.open(settings, HashingEmbedder())
    # 伪造一个"由别的模型建立"的向量库身份
    write_store_identity(
        settings,
        "qdrant",
        model_id="BAAI/bge-m3",
        model_rev="abc",
        dim=1024,
        active_collection="papers_v1",
    )

    with pytest.raises(LitError) as excinfo:
        VectorStore.open(settings, HashingEmbedder())
    assert excinfo.value.code == E_VECTOR_MODEL_MISMATCH


def test_dimension_mismatch_is_rejected(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with pytest.raises(LitError) as excinfo:
        VectorStore.open(settings, HashingEmbedder(dim=768))
    assert excinfo.value.code == E_VECTOR_DIM_MISMATCH


def test_reopen_keeps_points(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = VectorStore.open(settings, HashingEmbedder())
    store.upsert_papers(rows())

    reopened = VectorStore.open(settings, HashingEmbedder())
    assert reopened.count() == 3


def test_paper_text_prefers_title_then_abstract() -> None:
    assert paper_text({"title": "T", "abstract": "A"}) == "T\n\nA"
    assert paper_text({"title": "T", "abstract": ""}) == "T"
    assert paper_text({"title": "T", "abstract": None}) == "T"
