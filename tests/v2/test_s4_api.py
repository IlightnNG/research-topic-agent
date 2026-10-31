"""V2 S4 API surface: async run, SSE, timeline."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent_v2.api.app import create_app


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "fulltext").mkdir(parents=True)
    topics = [
        "Function calling improves API routing accuracy in agent systems. Tool routing reduces latency for multi-step agent workflows.",
        "Dense retrievers improve passage ranking accuracy on benchmarks. Rerankers improve recall for retrieval augmented systems.",
        "Hierarchical planners improve task decomposition in long horizon agents. Search budgets reduce branch expansion during planning efficiently.",
        "Episodic buffers improve context retention across conversation turns. Memory lookup improves persistence across multi turn sessions.",
        "Rubric judges improve scoring agreement with human annotators. Annotators calibrate agreement for reliable evaluation benchmarks.",
    ]
    with (root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for group, text in enumerate(topics):
            for index in range(4):
                pid = f"P{group}{index}"
                (root / "fulltext" / f"{pid}.txt").write_text(text, encoding="utf-8")
                handle.write(
                    json.dumps({"paper_id": pid, "title": pid, "abstract": text, "authors": [f"Author {group}"], "venue": "ACL", "year": 2025}) + "\n"
                )
    return root


def _wait(client: TestClient, run_id: str) -> str:
    for _ in range(100):
        state = str(client.get(f"/api/v2/runs/{run_id}").json()["state"])
        if state in {"succeeded", "failed"}:
            return state
        time.sleep(0.05)
    return "timeout"


def test_v2_async_run_events_and_report(tmp_path: Path) -> None:
    db_path = tmp_path / "v2.sqlite"
    app = create_app(db_path=db_path, corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/v2/runs", json={"topic_id": "agents", "limit": 20})
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        assert _wait(client, run_id) == "succeeded"

        with client.stream("GET", f"/api/v2/runs/{run_id}/events") as stream:
            body = "".join(stream.iter_text())
        assert "run.started" in body
        assert "section.delta" in body
        assert "run.finished" in body

        with client.stream(
            "GET",
            f"/api/v2/runs/{run_id}/events",
            headers={"Last-Event-ID": "1"},
        ) as replay:
            replayed = "".join(replay.iter_text())
        assert "run.started" not in replayed

        with sqlite3.connect(db_path) as conn:
            report_id = conn.execute(
                "SELECT report_id FROM reports WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        run_report = client.get(f"/api/v2/runs/{run_id}/report")
        assert run_report.status_code == 200
        assert run_report.json()["report_id"] == report_id
        report = client.get(f"/api/v2/reports/{report_id}")
        assert report.status_code == 200
        assert report.json()["sections"]


def test_v2_timeline_page(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "v2.sqlite", corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Report Workflow" in page.text
