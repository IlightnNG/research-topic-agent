"""3.3 / S1-S2: selector queries, preview and AI venue suggestions."""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.config import load_settings
from lit_agent.errors import E_SRC_NO_SELECTOR, LitError
from lit_agent.sources.preview import preview_selector
from lit_agent.sources.suggest import suggest_sources


def _settings() -> object:
    return load_settings(environ={}, dotenv_path=Path("none.env"))


class FakeAdapter:
    def __init__(self, works: list[dict]) -> None:
        self.works = works
        self.calls: list[dict] = []

    def fetch_works(self, *, since, selector, limit=None):
        self.calls.append({"since": since, "selector": selector, "limit": limit})
        return iter(self.works[:limit])


def _work(paper_id: str = "W1", title: str = "Tool use in agents") -> dict:
    return {
        "id": f"https://openalex.org/{paper_id}",
        "title": title,
        "publication_year": 2024,
        "doi": f"https://doi.org/10.1/{paper_id}",
        "primary_location": {
            "source": {"id": "https://openalex.org/S1", "display_name": "ACL"}
        },
        "authorships": [],
    }


def test_preview_returns_sample_and_passes_queries() -> None:
    adapter = FakeAdapter([_work("W1"), _work("W2", "Second")])
    result = preview_selector(
        _settings(), {"queries": ["tool use"], "from_year": 2024}, limit=2, adapter=adapter
    )

    assert result["sample_count"] == 2
    assert result["since"] == "2024-01-01"
    assert adapter.calls[0]["selector"]["queries"] == ["tool use"]


def test_preview_requires_selector() -> None:
    with pytest.raises(LitError) as exc:
        preview_selector(_settings(), {})
    assert exc.value.code == E_SRC_NO_SELECTOR


class FakeGateway:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_json(self, *args, **kwargs):
        return self.payload, None


def test_suggest_resolves_names_not_ids() -> None:
    gateway = FakeGateway(
        {"venues": ["ACL", "Unknown Venue"], "queries": ["LLM agents"], "from_year": 2023}
    )
    result = suggest_sources(
        _settings(),
        "LLM agents and tool use",
        gateway=gateway,
        resolver=lambda names: {"ACL": "S4363608652", "Unknown Venue": None},
    )

    assert result["source"] == "ai"
    assert result["venues"][0] == {
        "name": "ACL",
        "source_id": "S4363608652",
        "confidence": 0.9,
    }
    assert result["venues"][1]["confidence"] == 0.0
    assert result["queries"] == ["LLM agents"]


def test_suggest_without_gateway_falls_back() -> None:
    result = suggest_sources(_settings(), "retrieval augmented generation")
    assert result["source"] == "fallback"
    assert result["queries"]


def test_source_api_routes(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from lit_agent.api.app import create_app
    from lit_agent.sources import preview, suggest
    from tests.wiring import prepare

    monkeypatch.setattr(
        preview,
        "preview_selector",
        lambda settings, selector, limit=10: {
            "selector": selector,
            "since": "2024-01-01",
            "sample_count": 1,
            "items": [{"paper_id": "P1", "title": "T", "year": 2024, "source": "openalex"}],
        },
    )
    monkeypatch.setattr(
        suggest,
        "suggest_sources",
        lambda settings, scope, gateway=None: {
            "venues": [{"name": "ACL", "source_id": "S1", "confidence": 0.9}],
            "queries": ["agents"],
            "from_year": 2024,
            "source": "ai",
        },
    )
    client = TestClient(create_app(prepare(tmp_path)))

    preview_res = client.post(
        "/api/sources/preview", json={"selector": {"queries": ["agents"]}, "limit": 5}
    )
    assert preview_res.status_code == 200
    assert preview_res.json()["sample_count"] == 1

    suggest_res = client.post("/api/sources/suggest", json={"scope_statement": "LLM agents"})
    assert suggest_res.status_code == 200
    assert suggest_res.json()["venues"][0]["source_id"] == "S1"
