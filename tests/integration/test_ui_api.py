"""S1–S3 验收：run 列表 / PATCH topic / 异步 202 / abort / sections / 失败 run 404."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import LitError
from lit_agent.models.topic import Topic
from lit_agent.runtime import control
from lit_agent.runtime.runner import run_topic


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


def test_run_list_has_period_focus_and_report(client: TestClient) -> None:
    created = client.post(
        "/api/topics/ai-agents/run", json={"run_id": "s1-run", "focus_hint": "tool use"}
    )
    assert created.status_code == 200 and created.json()["state"] == "succeeded"

    payload = client.get("/api/topics/ai-agents/runs").json()
    item = payload["items"][0]
    assert item["id"] == "s1-run"
    assert item["period"], "period 必须由后端计算"
    assert item["focus_hint"] == "tool use"
    assert item["report_id"], "成功的 run 必须带 report_id"
    assert float(item["cost_usd"]) >= 0.0


def test_patch_topic_renames_and_archives(client: TestClient) -> None:
    patched = client.patch(
        "/api/topics/ai-agents", json={"name": "AI Agents v2", "status": "archived"}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "AI Agents v2"
    assert patched.json()["status"] == "archived"

    rejected = client.patch("/api/topics/ai-agents", json={"status": "active", "bogus": 1})
    assert rejected.status_code in (400, 422)


def test_async_run_returns_202_and_finishes(client: TestClient) -> None:
    started = client.post(
        "/api/topics/ai-agents/run", json={"run_id": "s2-async", "wait": False}
    )
    assert started.status_code == 202
    assert started.json()["run_id"] == "s2-async"

    state = None
    for _ in range(200):
        response = client.get("/api/runs/s2-async")
        state = response.json().get("state") if response.status_code == 200 else None
        if state in {"succeeded", "failed", "aborted"}:
            break
        time.sleep(0.05)
    assert state == "succeeded", f"异步 run 未完成：{state}"


def test_abort_mid_run_fails_with_abort_code(client: TestClient) -> None:
    control.request_abort("s2-abort")
    response = client.post("/api/topics/ai-agents/run", json={"run_id": "s2-abort"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "failed"
    run = client.get("/api/runs/s2-abort").json()
    assert run["error_code"] == "E_RUN_ABORTED"


def test_control_endpoints_validate_run_existence(client: TestClient) -> None:
    # S9：pause/resume/inject 已实装 → 未知 run 必须是 404（而不是 501）
    for action in ("pause", "resume"):
        response = client.post(f"/api/runs/any/{action}")
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "E_NOT_FOUND"
    injected = client.post("/api/runs/any/inject", json={"prompt": "hint"})
    assert injected.status_code == 404


def test_report_has_sections_from_claims(tmp_path: Path) -> None:
    """S12：报告分节由 claims 分组落库（Findings N），不再是 API 临时派生。"""
    from lit_agent.db.repo import papers as paper_repo
    from lit_agent.models.paper import Paper

    settings = prepare(tmp_path / "sections")
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id="P-sections",
                        title="Tool use for agents",
                        abstract="tool use improves task success in agent systems",
                        source="arxiv",
                    )
                ],
            )
    finally:
        engine.dispose()

    with TestClient(create_app(settings)) as client:
        client.post("/api/topics/ai-agents/run", json={"run_id": "s3-sections"})
        report = client.get("/api/runs/s3-sections/report").json()

    assert report["claims"], "报告应含 claims"
    sections = report["sections"]
    assert sections, "报告应有分节"
    assert any(section.get("claim_indexes") for section in sections), "分节必须能回指 claims"


def test_failed_run_report_is_404(tmp_path: Path) -> None:
    settings = prepare(tmp_path / "fail")

    def boom(ctx):  # noqa: ANN001
        raise LitError("E_SRC_TIMEOUT", "source timed out")

    result = run_topic(settings, "ai-agents", run_id="s3-fail", stages={"ingest": boom})
    assert result["state"] == "failed"

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/runs/s3-fail/report")
        assert response.status_code == 404
        assert response.json()["code"] == "E_NOT_FOUND"
