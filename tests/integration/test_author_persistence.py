"""F2（P0/G-01）：论文入库必须同时落作者与署名关系。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.author import Author
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.runner import run_topic
from lit_agent.stores.graph import GraphStore
from lit_agent.stores.rebuild import rebuild_graph


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    return settings


def counts(settings: Settings) -> dict[str, int]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return {
                "papers": int(conn.execute(text("SELECT COUNT(*) FROM papers")).scalar_one()),
                "authors": int(conn.execute(text("SELECT COUNT(*) FROM authors")).scalar_one()),
                "links": int(conn.execute(text("SELECT COUNT(*) FROM paper_authors")).scalar_one()),
            }
    finally:
        engine.dispose()


def test_upsert_many_persists_authors_and_links(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    papers = [
        Paper(
            paper_id="arxiv:1",
            title="One",
            abstract="a",
            source="arxiv",
            authors=[
                Author(author_id="A1", name="Ada", name_norm="ada"),
                Author(author_id="A2", name="Bob", name_norm="bob"),
            ],
        ),
        Paper(
            paper_id="arxiv:2",
            title="Two",
            abstract="b",
            source="arxiv",
            authors=[Author(author_id="A1", name="Ada", name_norm="ada")],
        ),
    ]
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            paper_repo.upsert_many(conn, papers)
    finally:
        engine.dispose()

    got = counts(settings)
    assert got == {"papers": 2, "authors": 2, "links": 3}, got


def test_upsert_many_author_write_is_idempotent(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    paper = Paper(
        paper_id="arxiv:1",
        title="One",
        source="arxiv",
        authors=[Author(author_id="A1", name="Ada", name_norm="ada")],
    )
    for _ in range(3):
        engine = make_engine(settings)
        try:
            with connect(engine, immediate=True) as conn:
                paper_repo.upsert_many(conn, [paper])
        finally:
            engine.dispose()

    got = counts(settings)
    assert got == {"papers": 1, "authors": 1, "links": 1}, got


def test_authors_reach_the_graph_and_metrics(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id="arxiv:1",
                        title="One",
                        abstract="agents use tools",
                        source="arxiv",
                        authors=[
                            Author(author_id="A1", name="Ada", name_norm="ada"),
                            Author(author_id="A2", name="Bob", name_norm="bob"),
                        ],
                    )
                ],
            )
    finally:
        engine.dispose()

    result = run_topic(settings, "ai-agents", run_id="f2-run")
    assert result["state"] == "succeeded"

    rebuild_graph(settings)
    with GraphStore.open(settings) as store:
        graph_counts = store.counts()
    assert graph_counts["authors"] == 2, graph_counts
    assert graph_counts["authorships"] == 2, graph_counts
    assert graph_counts["papers"] == 1, graph_counts
