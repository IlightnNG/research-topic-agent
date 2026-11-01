"""M6-P01: report API, error envelope, minimal UI."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent_v2.api.app import create_app


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "fulltext").mkdir(parents=True)
    topics = [
        "Tool routing improves agent success on benchmark tasks.",
        "Dense retrieval improves passage ranking quality on benchmarks.",
        "Hierarchical planning improves task decomposition for agents.",
    ]
    with (root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for group, text in enumerate(topics):
            for index in range(4):
                pid = f"P{group}{index}"
                (root / "fulltext" / f"{pid}.txt").write_text(text, encoding="utf-8")
                handle.write(
                    json.dumps(
                        {
                            "paper_id": pid,
                            "title": f"Study {pid}",
                            "abstract": text,
                            "authors": [f"Author {group}"],
                            "venue": "ACL",
                            "year": 2025,
                        }
                    )
                    + "\n"
                )
    return root


def _wait(client: TestClient, run_id: str) -> str:
    for _ in range(100):
        state = str(client.get(f"/api/v2/runs/{run_id}").json()["state"])
        if state in {"succeeded", "failed"}:
            return state
        time.sleep(0.05)
    return "timeout"


def test_report_api_and_ui(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "v2.sqlite", corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/v2/runs", json={"topic_id": "agents", "limit": 12})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert _wait(client, run_id) == "succeeded"

        link = client.get(f"/api/v2/runs/{run_id}/report")
        assert link.status_code == 200
        report_id = link.json()["report_id"]
        report = client.get(f"/api/v2/reports/{report_id}")
        assert report.status_code == 200
        payload = report.json()
        assert payload["report"]["content_md"]
        assert payload["sections"]
        assert any(section["kind"] == "paper_index" for section in payload["sections"])

        page = client.get("/")
        assert page.status_code == 200
        assert "Report Workflow" in page.text
        assert "Report sections" in page.text
        assert "EventSource" in page.text


def test_error_envelope(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "v2.sqlite", corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        missing = client.get("/api/v2/runs/not-a-run")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "E_RUN_NOT_FOUND"

        missing_report = client.get("/api/v2/reports/not-a-report")
        assert missing_report.status_code == 404
        assert missing_report.json()["error"]["code"] == "E_REPORT_NOT_FOUND"

        invalid = client.post("/api/v2/runs", json={"limit": 0})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "E_INVALID_REQUEST"

        no_corpus = create_app(
            db_path=tmp_path / "empty.sqlite", corpus_root=tmp_path / "does-not-exist"
        )
        with TestClient(no_corpus) as empty:
            response = empty.post("/api/v2/runs", json={"topic_id": "agents", "limit": 1})
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "E_CORPUS_NOT_FOUND"
