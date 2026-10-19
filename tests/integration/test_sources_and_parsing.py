"""Step 1.6 同步 / Step 1.7 解析：端到端（respx 拦截 OpenAlex，不联网）。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import E_SRC_NO_SELECTOR, LitError
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.parsing.pipeline import parse_papers
from lit_agent.sources.openalex import WORK_ENDPOINT, OpenAlexAdapter
from lit_agent.sources.sync import sync_topic
from lit_agent.stores.files import paper_path


def make_work(suffix: str) -> dict:
    return {
        "id": f"https://openalex.org/W{suffix}",
        "doi": f"https://doi.org/10.1000/{suffix}",
        "title": f"LLM agents paper {suffix}",
        "publication_year": 2024,
        "publication_date": "2024-03-01",
        "updated_date": "2024-04-01T00:00:00Z",
        "language": "en",
        "cited_by_count": 3,
        "open_access": {"is_oa": True},
        "primary_location": {
            "source": {"id": "https://openalex.org/S42", "display_name": "NeurIPS"}
        },
        "best_oa_location": {"pdf_url": f"https://example.org/{suffix}.pdf"},
        "referenced_works": [],
        "authorships": [
            {"author": {"id": "https://openalex.org/A1", "display_name": "Ada Lovelace"}}
        ],
        "abstract_inverted_index": {"agents": [0], "tools": [1]},
    }


def prepare(tmp_path: Path, *, venue_ids: list[str] | None = None) -> Settings:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(
                conn,
                Topic(id="ai-agents", name="AI Agents", scope_statement="llm agents"),
            )
            topic_repo.upsert_sources(
                conn,
                "ai-agents",
                [
                    (
                        "openalex",
                        {
                            "venue_ids": venue_ids if venue_ids is not None else ["S42"],
                            "from_year": 2023,
                            "type": "article",
                        },
                    )
                ],
            )
    finally:
        engine.dispose()
    return settings


def fake_adapter() -> OpenAlexAdapter:
    return OpenAlexAdapter(client=httpx.Client())


@respx.mock
def test_sync_is_incremental_and_idempotent(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    respx.get(WORK_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json={"meta": {"next_cursor": None}, "results": [make_work("1"), make_work("2")]},
        )
    )

    first = sync_topic(settings, "ai-agents", adapter=fake_adapter())
    assert first["fetched"] == 2
    assert first["papers_new"] == 2
    assert first["raw_records"] == 2

    second = sync_topic(settings, "ai-agents", adapter=fake_adapter())
    assert second["papers_new"] == 0, "同一 fixture 重跑不得新增"
    assert second["papers_updated"] == 2


@respx.mock
def test_seeded_paper_fields_are_persisted(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    respx.get(WORK_ENDPOINT).mock(
        return_value=httpx.Response(
            200, json={"meta": {"next_cursor": None}, "results": [make_work("7")]}
        )
    )
    sync_topic(settings, "ai-agents", adapter=fake_adapter())

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = paper_repo.get(conn, "10.1000/7")._mapping
    finally:
        engine.dispose()
    assert row["venue_id"] == "S42"
    assert row["source_id"] == "W7"
    assert row["is_oa"] == 1
    assert row["language"] == "en"


def test_empty_venue_ids_is_explicit_failure(tmp_path: Path) -> None:
    settings = prepare(tmp_path, venue_ids=[])
    try:
        sync_topic(settings, "ai-agents", adapter=fake_adapter())
    except LitError as exc:
        assert exc.code == E_SRC_NO_SELECTOR
    else:  # pragma: no cover
        raise AssertionError("空 selector 必须报 E_SRC_NO_SELECTOR")


def _write_text_pdf(path: Path, text: str) -> None:
    import pymupdf

    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(str(path))
    document.close()


def test_parsing_pipeline_marks_ok_and_writes_chunks(tmp_path: Path) -> None:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id="W-ok",
                        title="Parsable",
                        source="openalex",
                        oa_pdf_url="https://example.org/ok.pdf",
                    )
                ],
            )
    finally:
        engine.dispose()
    _write_text_pdf(
        paper_path(settings, "W-ok"),
        "Sentence one about agents. Sentence two about tools. Sentence three about planning.",
    )

    result = parse_papers(settings, token_budget=40)
    assert result["ok"] == 1
    assert result["chunks"] >= 1
    assert result["failed"] == 0

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = paper_repo.get(conn, "W-ok")._mapping
    finally:
        engine.dispose()
    assert row["parse_status"] == "ok"
    assert row["n_chunks"] >= 1

    # 已解析的不再重复处理
    again = parse_papers(settings, token_budget=40)
    assert again["candidates"] == 0


def test_parsing_pipeline_marks_failed_without_raising(tmp_path: Path) -> None:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id="W-bad",
                        title="Broken",
                        source="openalex",
                        oa_pdf_url="https://example.org/bad.pdf",
                    )
                ],
            )
    finally:
        engine.dispose()
    broken = paper_path(settings, "W-bad")
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"%PDF-1.4 broken body without xref")

    result = parse_papers(settings)
    assert result["failed"] == 1
    assert result["errors"][0]["paper_id"] == "W-bad"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = paper_repo.get(conn, "W-bad")._mapping
    finally:
        engine.dispose()
    assert row["parse_status"] == "failed"


def test_selector_snapshot_is_stored(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            sources = topic_repo.get_sources(conn, "ai-agents")
    finally:
        engine.dispose()
    assert sources["openalex"]["venue_ids"] == ["S42"]
    assert json.dumps(sources["openalex"])  # 可序列化
