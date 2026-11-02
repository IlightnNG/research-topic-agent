"""Platform API e2e: topics -> run -> trace -> report -> paper."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent_v2.api.app import create_app


class FakeLLM:
    def __init__(self) -> None:
        self.node_calls = 0
        self.section_calls = 0
        self.lock = threading.Lock()

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        system = messages[0]["content"]
        if "evidence-grounded report sections" in system:
            with self.lock:
                self.section_calls += 1
            return {"body": "Evidence summary [C1]. Second finding [C2]."}, None
        with self.lock:
            self.node_calls += 1
            index = self.node_calls
        actions = [
            {
                "action": "tool",
                "calls": [
                    {
                        "id": "c1",
                        "name": "corpus.papers",
                        "args": {"root": str(ROOT)},
                    }
                ],
            },
            {
                "action": "tool",
                "calls": [
                    {
                        "id": "c2",
                        "name": "claims.extract",
                        "args": {"paper_id": "P1", "text": "Tool use improves success."},
                    },
                    {
                        "id": "c3",
                        "name": "claims.extract",
                        "args": {"paper_id": "P2", "text": "Citation coverage measures support."},
                    },
                ],
            },
            {
                "action": "tool",
                "calls": [
                    {
                        "id": "c4",
                        "name": "report.plan",
                        "args": {
                            "papers": [
                                {"paper_id": "P1"},
                                {"paper_id": "P2"},
                            ]
                        },
                    }
                ],
            },
            {
                "action": "tool",
                "calls": [
                    {
                        "id": "w1",
                        "name": "report.write_section",
                        "args": {
                            "section": {
                                "section_id": "overview",
                                "kind": "overview",
                                "title": "Overview",
                            },
                            "claims": [
                                {"claim_id": "C1", "paper_id": "P1", "quote": "Tool use improves success."},
                                {"claim_id": "C2", "paper_id": "P2", "quote": "Citation coverage measures support."},
                            ],
                        },
                    }
                ],
            },
            {
                "action": "tool",
                "calls": [
                    {
                        "id": "p1",
                        "name": "report.persist",
                        "args": {
                            "root": str(ROOT / "out"),
                            "title": "T",
                            "content_md": "Evidence [C1] [C2].",
                            "claims": [
                                {"claim_id": "C1", "paper_id": "P1", "quote": "Tool use improves success."},
                                {"claim_id": "C2", "paper_id": "P2", "quote": "Citation coverage measures support."},
                            ],
                        },
                    }
                ],
            },
            {
                "action": "final",
                "outputs": {
                    "title": "T",
                    "content_md": "Evidence [C1] [C2].",
                    "claims": [
                        {"claim_id": "C1", "paper_id": "P1", "quote": "Tool use improves success."},
                        {"claim_id": "C2", "paper_id": "P2", "quote": "Citation coverage measures support."},
                    ],
                    "path": str(ROOT / "out" / "report.json"),
                },
            },
        ]
        return actions[min(index - 1, len(actions) - 1)], None


ROOT = Path()


def test_platform_api_e2e(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIT_V2_DEMO_CHAIN", "single")
    global ROOT
    ROOT = tmp_path
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    papers = [
        {"paper_id": "P1", "title": "A", "abstract": "Tool use improves success."},
        {"paper_id": "P2", "title": "B", "abstract": "Citation coverage measures support."},
    ]
    (corpus / "papers.jsonl").write_text(
        "\n".join(json.dumps(paper) for paper in papers) + "\n", encoding="utf-8"
    )
    app = create_app(
        db_path=tmp_path / "api.sqlite",
        corpus_root=corpus,
        platform_llm=FakeLLM(),
    )
    client = TestClient(app)

    topics = client.get("/api/v2/topics")
    assert topics.status_code == 200
    assert any(topic["direction"] == "AI agents" for topic in topics.json())

    created = client.post(
        "/api/v2/topics/topic-ai-agents/runs",
        json={"focus_hint": "evaluation", "language": "en"},
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]

    state = "running"
    for _ in range(100):
        payload = client.get(f"/api/v2/runs/{run_id}").json()
        state = payload["state"]
        if state != "running":
            break
        time.sleep(0.05)
    assert state == "succeeded", payload

    trace = client.get(f"/api/v2/runs/{run_id}/trace").json()
    assert trace["nodes"][0]["node_id"] == "report.generate"
    assert any(event["type"] == "tool.called" for event in trace["events"])
    assert any(event["type"] == "tool.result" for event in trace["events"])

    link = client.get(f"/api/v2/runs/{run_id}/report")
    assert link.status_code == 200, link.text
    report_id = link.json()["report_id"]
    report = client.get(f"/api/v2/reports/{report_id}").json()
    assert report["report"]["title"] == "T"
    assert report["sections"]
    assert report["sections"][0]["paper_links"]

    paper = client.get("/api/v2/papers/P1")
    assert paper.status_code == 200
    assert paper.json()["title"] == "A"

    conversation = client.post("/api/v2/topics/topic-ai-agents/conversations")
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    reply = client.post(
        f"/api/v2/conversations/{conversation_id}/messages",
        json={"content": "Does tool use improve success?"},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["content"]
    assert reply.json()["citations"]

    # Older projects recorded context.compacted without node_id; trace must
    # attribute it to the active node for display inside that node.
    with sqlite3.connect(tmp_path / "api.sqlite") as conn:
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO run_events(id,run_id,seq,type,node_id,payload_json,ts)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                "legacy-context",
                run_id,
                seq,
                "context.compacted",
                None,
                json.dumps({"step": 6, "before": 20000, "after": 12000}),
                "2026-11-01T00:00:00+00:00",
            ),
        )
    trace = client.get(f"/api/v2/runs/{run_id}/trace").json()
    context_events = [event for event in trace["events"] if event["type"] == "context.compacted"]
    assert context_events
    assert context_events[-1]["node_id"] == "report.generate"

    assert client.delete(f"/api/v2/runs/{run_id}").status_code == 204
    assert client.get(f"/api/v2/runs/{run_id}").status_code == 404
