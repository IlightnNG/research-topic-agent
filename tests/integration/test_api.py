"""Step 1.15 API + SSE 验收（TestClient，无网络）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from lit_agent.config import Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.topic import Topic


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="llm agents"))
    finally:
        engine.dispose()
    return settings


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(prepare(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_schema(client: TestClient) -> None:
    payload = client.get("/api/health").json()
    assert payload["ok"] is True
    assert payload["sqlite"]["schema_version"] == "1.0"
    assert payload["sqlite"]["tables"] == 24


def test_topics_crud(client: TestClient) -> None:
    created = client.post(
        "/api/topics",
        json={
            "id": "communications",
            "name": "Comms",
            "scope_statement": "wireless networks",
            "sources": [{"source": "openalex", "selector": {"venue_ids": ["S1"]}}],
        },
    )
    assert created.status_code == 201
    assert created.json()["sources"] == ["openalex"]

    listed = client.get("/api/topics").json()
    assert {item["id"] for item in listed} == {"ai-agents", "communications"}

    detail = client.get("/api/topics/communications").json()
    assert detail["sources"]["openalex"]["venue_ids"] == ["S1"]


def test_run_trigger_and_events(client: TestClient) -> None:
    started = client.post("/api/topics/ai-agents/run", json={"run_id": "run-api"})
    assert started.status_code == 200
    assert started.json()["state"] == "succeeded"

    run = client.get("/api/runs/run-api").json()
    assert run["state"] == "succeeded"
    assert run["stage"] == "evaluate"  # Phase 2：十节点收尾

    events = client.get("/api/runs/run-api/events").json()
    assert events["count"] >= 5
    assert [item["seq"] for item in events["items"]] == list(range(1, events["count"] + 1))

    page = client.get("/api/runs/run-api/events", params={"after_seq": 1}).json()
    assert page["items"][0]["seq"] == 2

    assert client.get("/api/metrics/summary").json()["runs"] >= 1


def test_unknown_run_is_404(client: TestClient) -> None:
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "E_NOT_FOUND"


def test_chat_is_implemented_and_graph_is_501(client: TestClient) -> None:
    chat = client.get("/api/topics/ai-agents/chat")
    assert chat.status_code == 200
    assert chat.json()["messages"] == []

    graph = client.get("/api/graph/authors/A1")
    assert graph.status_code == 501


def test_openapi_exposes_contract_paths(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"])
    for expected in (
        "/api/health",
        "/api/topics",
        "/api/topics/{topic_id}/run",
        "/api/runs/{run_id}",
        "/api/runs/{run_id}/events",
        "/api/runs/{run_id}/stream",
        "/api/metrics/summary",
        "/api/sources",
    ):
        assert expected in paths, expected


def test_sse_replays_and_ends(client: TestClient) -> None:
    client.post("/api/topics/ai-agents/run", json={"run_id": "run-sse"})

    with client.stream("GET", "/api/runs/run-sse/stream") as response:
        body = "".join(response.iter_text())

    assert "id: 1" in body
    assert "event: end" in body
    assert '"state": "succeeded"' in body


def test_sse_after_seq_skips_earlier_events(client: TestClient) -> None:
    client.post("/api/topics/ai-agents/run", json={"run_id": "run-sse2"})

    with client.stream("GET", "/api/runs/run-sse2/stream", params={"after_seq": 2}) as response:
        body = "".join(response.iter_text())

    assert "id: 1\n" not in body
    assert "id: 3" in body
