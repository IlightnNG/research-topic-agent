"""三库重建与对账（Step 1.5 出口 D6）：SQLite 是唯一真相源。"""

from __future__ import annotations

from pathlib import Path

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.repo import authors as author_repo
from lit_agent.db.repo import citations as citation_repo
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.author import Author
from lit_agent.models.paper import Paper
from lit_agent.stores.graph import GraphStore
from lit_agent.stores.rebuild import rebuild_graph, rebuild_vector, verify_counts
from lit_agent.stores.vector import HashingEmbedder, close_clients


def seed(settings: Settings) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            paper_repo.upsert_many(
                conn,
                [
                    Paper(paper_id="W1", title="LLM agents", source="openalex", year=2024),
                    Paper(paper_id="W2", title="Wireless MIMO", source="openalex", year=2023),
                ],
            )
            author_repo.upsert_many(
                conn,
                [
                    Author(author_id="A1", name="Ada", name_norm="ada"),
                    Author(author_id="A2", name="Bob", name_norm="bob"),
                ],
            )
            author_repo.link_many(conn, "W1", ["A1"])
            author_repo.link_many(conn, "W2", ["A2"])
            citation_repo.insert_ignore_many(conn, [("W1", "W2")])
    finally:
        engine.dispose()


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    seed(settings)
    return settings


def test_rebuild_graph_matches_sqlite(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = rebuild_graph(settings)

    assert result["counts"]["papers"] == 2
    assert result["counts"]["authors"] == 2
    assert result["counts"]["citations"] == 1
    assert result["counts"]["authorships"] == 2


def test_rebuild_vector_creates_points(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = rebuild_vector(settings, embedder=HashingEmbedder())

    assert result["points"] == 2
    assert result["model_id"] == HashingEmbedder.model_id


def test_verify_counts_passes_after_rebuild(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    rebuild_graph(settings)
    rebuild_vector(settings, embedder=HashingEmbedder())

    report = verify_counts(settings, embedder=HashingEmbedder())
    assert report["ok"], report["mismatches"]
    assert report["sqlite"]["papers"] == 2


def test_verify_counts_detects_graph_drift(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    rebuild_graph(settings)
    rebuild_vector(settings, embedder=HashingEmbedder())

    # 绕过重建，直接往图里塞一个 SQLite 不存在的节点 → 必须被发现
    with GraphStore.open(settings) as store:
        store.upsert_papers(
            [
                {
                    "paper_id": "GHOST",
                    "title": "ghost",
                    "year": 2020,
                    "source": "openalex",
                    "venue_id": None,
                    "discovered_at": "2026-10-19T00:00:00Z",
                }
            ]
        )

    report = verify_counts(settings, embedder=HashingEmbedder())
    assert report["ok"] is False
    assert any("graph.papers" in item for item in report["mismatches"])


def test_verify_counts_detects_missing_vector_collection(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    rebuild_graph(settings)
    rebuild_vector(settings, embedder=HashingEmbedder())

    # 模拟"向量库丢失"：删掉 collection 后对账必须失败，而不是自动建一个空库报 ok
    from lit_agent.selftest import assert_ascii_path
    from lit_agent.stores.vector import get_client

    client = get_client(assert_ascii_path(settings.storage.qdrant_dir))
    client.delete_collection(settings.vector.active_collection)

    report = verify_counts(settings, embedder=HashingEmbedder())
    assert report["ok"] is False
    assert any("collection" in item for item in report["mismatches"])


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    close_clients()

    first = rebuild_graph(settings)
    second = rebuild_graph(settings)
    assert first["counts"] == second["counts"]

    rebuild_vector(settings, embedder=HashingEmbedder())
    again = rebuild_vector(settings, embedder=HashingEmbedder())
    assert again["points"] == 2
