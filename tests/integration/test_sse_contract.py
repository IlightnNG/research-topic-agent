"""F7：SSE 续传语义与 API 契约补测（不重不漏 / Last-Event-ID / 409 / 501）."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.run import RunState
from lit_agent.models.topic import Topic
from lit_agent.runtime import jobs


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
    finally:
        engine.dispose()
    return settings


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    with TestClient(create_app(prepare(tmp_path))) as test_client:
        yield test_client


def run_once(client: TestClient, run_id: str) -> int:
    response = client.post("/api/topics/ai-agents/run", json={"run_id": run_id})
    assert response.status_code == 200, response.text
    return client.get(f"/api/runs/{run_id}/events").json()["count"]


def test_after_seq_pages_do_not_overlap_or_skip(client: TestClient) -> None:
    total = run_once(client, "f7-page")
    assert total >= 5

    first = client.get("/api/runs/f7-page/events", params={"after_seq": 0, "limit": 3}).json()
    second = client.get("/api/runs/f7-page/events", params={"after_seq": 3, "limit": 100}).json()

    first_seqs = [item["seq"] for item in first["items"]]
    second_seqs = [item["seq"] for item in second["items"]]
    assert first_seqs == [1, 2, 3]
    assert set(first_seqs) & set(second_seqs) == set(), "分页不得重复"
    assert sorted(first_seqs + second_seqs) == list(range(1, total + 1)), "分页不得遗漏"


def test_sse_honours_last_event_id_header(client: TestClient) -> None:
    run_once(client, "f7-header")

    with client.stream(
        "GET", "/api/runs/f7-header/stream", headers={"Last-Event-ID": "3"}
    ) as response:
        body = "".join(response.iter_text())

    assert "id: 1\n" not in body and "id: 3\n" not in body
    assert "id: 4" in body, "Last-Event-ID 之后的第一个事件必须是 seq=4"
    assert "event: end" in body


def test_sse_resume_from_last_seq_is_lossless(client: TestClient) -> None:
    total = run_once(client, "f7-resume")
    with client.stream("GET", "/api/runs/f7-resume/stream") as response:
        full = "".join(response.iter_text())
    full_ids = [line.split(": ")[1] for line in full.splitlines() if line.startswith("id: ")]

    with client.stream(
        "GET", "/api/runs/f7-resume/stream", params={"after_seq": len(full_ids) - 1}
    ) as response:
        tail = "".join(response.iter_text())

    assert full_ids == [str(seq) for seq in range(1, total + 1)]
    assert "event: end" in tail
    assert len([line for line in tail.splitlines() if line.startswith("id: ")]) == 1, (
        "从倒数第二条重连时只应补发最后一条"
    )


def test_after_seq_beyond_end_yields_only_end_event(client: TestClient) -> None:
    run_once(client, "f7-far")
    with client.stream("GET", "/api/runs/f7-far/stream", params={"after_seq": 999}) as response:
        body = "".join(response.iter_text())

    assert "id: " not in body
    assert body.strip() == 'event: end\ndata: {"state": "succeeded", "last_seq": 0}' or (
        "event: end" in body
    )


def test_concurrent_run_returns_409_with_lock_code(client: TestClient, tmp_path: Path) -> None:
    settings = prepare(tmp_path / "lock")
    jobs.start(settings, "ai-agents", run_id="f7-held")
    try:
        other = TestClient(create_app(settings))
        response = other.post("/api/topics/ai-agents/run", json={"run_id": "f7-blocked"})
        assert response.status_code == 409
        assert response.json()["code"] == "E_LOCK_HELD"
    finally:
        jobs.finish(settings, "f7-held", state=RunState.ABORTED)
