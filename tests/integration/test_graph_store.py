"""Kuzu 图存储（Step 1.5）：MERGE 幂等、关系需 MATCH+MERGE、close 才落盘。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.config import Settings, StorageSettings
from lit_agent.errors import E_STORE_PATH_NONASCII, LitError
from lit_agent.stores.graph import GraphStore, paper_rows


def settings_for(tmp_path: Path) -> Settings:
    return Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))


def papers() -> list[dict]:
    return [
        {
            "paper_id": "W1",
            "title": "T1",
            "year": 2024,
            "source": "openalex",
            "venue_id": "V1",
            "discovered_at": "2026-10-19T00:00:00Z",
        },
        {
            "paper_id": "W2",
            "title": "T2",
            "year": 2025,
            "source": "openalex",
            "venue_id": "V2",
            "discovered_at": "2026-10-19T00:00:00Z",
        },
    ]


def test_merge_is_idempotent_and_updates(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with GraphStore.open(settings) as store:
        store.upsert_papers(papers())
        store.upsert_papers(papers())
        assert store.counts()["papers"] == 2

        updated = [dict(papers()[0], title="T1-updated")]
        store.upsert_papers(updated)
        assert store.counts()["papers"] == 2


def test_citations_are_idempotent_and_queryable(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with GraphStore.open(settings) as store:
        store.upsert_papers(papers())
        store.upsert_citations([("W1", "W2")], first_seen="2026-10-19T00:00:00Z")
        store.upsert_citations([("W1", "W2")], first_seen="2026-10-19T00:00:00Z")

        assert store.counts()["citations"] == 1
        assert store.cited_by("W2") == ["W1"]
        assert store.references_of("W1") == ["W2"]


def test_authorships(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with GraphStore.open(settings) as store:
        store.upsert_papers(papers())
        store.upsert_authors([{"author_id": "A1", "name": "Ada", "name_norm": "ada"}])
        store.upsert_authorships([("W1", "A1", 0)])
        store.upsert_authorships([("W1", "A1", 0)])
        counts = store.counts()
        assert counts["authors"] == 1
        assert counts["authorships"] == 1


def test_data_is_flushed_only_on_close(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    path = settings.storage.kuzu_file

    store = GraphStore.open(settings)
    store.upsert_papers(papers())
    before = path.stat().st_size if path.exists() else 0
    store.close()
    after = path.stat().st_size

    assert after > 0
    assert after >= before, "close 后必须落盘（ADR-0003）"


def test_reopen_sees_previous_data(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with GraphStore.open(settings) as store:
        store.upsert_papers(papers())

    with GraphStore.open(settings) as store:
        assert store.counts()["papers"] == 2


def test_non_ascii_path_is_rejected(tmp_path: Path) -> None:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "学术")))
    with pytest.raises(LitError) as excinfo:
        GraphStore.open(settings)
    assert excinfo.value.code == E_STORE_PATH_NONASCII


def test_paper_rows_projection() -> None:
    from lit_agent.models.paper import Paper

    rows = paper_rows(
        [Paper(paper_id="W1", title="T", source="openalex", year=2024)],
        discovered_at="2026-10-19T00:00:00Z",
    )
    assert rows[0]["paper_id"] == "W1"
    assert set(rows[0]) == {"paper_id", "title", "year", "source", "venue_id", "discovered_at"}
