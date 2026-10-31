"""3.5 / S1-S3: direct Report workflow endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from tests.wiring import prepare


def test_report_workflow_endpoint(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=5)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/topics/ai-agents/report-workflow",
            json={"limit": 5, "run_id": "api-direct"},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"] == "succeeded"
    assert payload["papers"] == 5
    assert payload["report_id"]


def test_report_workflow_endpoint_404(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/topics/nope/report-workflow", json={"limit": 5})
    assert response.status_code == 404
