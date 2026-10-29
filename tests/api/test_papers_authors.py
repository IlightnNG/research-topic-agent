"""3.2 / S10–S11：PDF 端点与作者面板 API。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.wiring import prepare

from lit_agent.api.app import create_app
from lit_agent.db.session import connect, make_engine


def _seed_author_links(settings, pdf: Path) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text("UPDATE papers SET pdf_path = :p WHERE paper_id = 'P0'"), {"p": str(pdf)}
            )
            conn.execute(
                text(
                    "INSERT INTO authors(author_id, name, name_norm, row_updated_at)"
                    " VALUES ('A1', 'Ada Lovelace', 'ada lovelace', '2026-01-01')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO authors(author_id, name, name_norm, row_updated_at)"
                    " VALUES ('A2', 'Alan Turing', 'alan turing', '2026-01-01')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO paper_authors(paper_id, author_id, position, is_corresponding)"
                    " VALUES ('P0', 'A1', 1, 1), ('P1', 'A1', 1, 0), ('P1', 'A2', 2, 0)"
                )
            )
    finally:
        engine.dispose()


def test_pdf_endpoint_and_range(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nhello pdf\n")
    _seed_author_links(settings, pdf)
    client = TestClient(create_app(settings))

    full = client.get("/api/papers/P0/pdf")
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("application/pdf")
    assert full.content.startswith(b"%PDF")

    part = client.get("/api/papers/P0/pdf", headers={"Range": "bytes=0-3"})
    assert part.status_code == 206
    assert part.content == b"%PDF"
    assert part.headers["content-range"].startswith("bytes 0-3/")


def test_pdf_missing_is_404(tmp_path: Path) -> None:
    client = TestClient(create_app(prepare(tmp_path, papers=1)))
    response = client.get("/api/papers/P0/pdf")
    assert response.status_code == 404
    assert response.json()["code"] == "E_NOT_FOUND"


def test_paper_authors_are_objects(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    _seed_author_links(settings, tmp_path / "none.pdf")
    client = TestClient(create_app(settings))

    payload = client.get("/api/papers/P0").json()
    assert payload["authors"][0]["author_id"] == "A1"
    assert payload["authors"][0]["name"] == "Ada Lovelace"


def test_author_profile_and_coauthors(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    _seed_author_links(settings, tmp_path / "none.pdf")
    client = TestClient(create_app(settings))

    payload = client.get("/api/authors/A1").json()
    assert payload["name"] == "Ada Lovelace"
    assert {paper["paper_id"] for paper in payload["papers"]} == {"P0", "P1"}
    assert payload["coauthors"][0]["author_id"] == "A2"

    missing = client.get("/api/authors/nope")
    assert missing.status_code == 404
