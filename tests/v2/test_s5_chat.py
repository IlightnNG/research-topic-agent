"""V2 S5 chat tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent_v2.api.app import create_app
from lit_agent_v2.domains.chat.answer import ChatService, stream_reply
from lit_agent_v2.domains.report.ingest import LocalCorpus


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "fulltext").mkdir(parents=True)
    text = "Tool use improves agent success. Agents solve tasks with tools."
    (root / "papers.jsonl").write_text(
        json.dumps({"paper_id": "P1", "title": "Tool use", "abstract": text}) + "\n",
        encoding="utf-8",
    )
    (root / "fulltext" / "P1.txt").write_text(text, encoding="utf-8")
    return root


def test_chat_answers_with_citation(tmp_path: Path) -> None:
    reply = ChatService(LocalCorpus(_corpus(tmp_path))).answer(
        topic_id="agents", message="tool use"
    )
    assert reply.answered is True
    assert reply.citations
    assert reply.text.startswith("According to [P1]")


def test_chat_refuses_without_evidence(tmp_path: Path) -> None:
    reply = ChatService(LocalCorpus(_corpus(tmp_path))).answer(
        topic_id="agents", message="zzz"
    )
    assert reply.answered is False
    # Token stream always ends with done.
    assert stream_reply(reply)


def test_chat_api_and_stream(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "v2.sqlite", corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/chat", json={"topic_id": "agents", "message": "tool use"}
        )
        assert response.status_code == 200
        assert response.json()["citations"]
        with client.stream(
            "GET", "/api/v2/chat/stream", params={"topic_id": "agents", "message": "tool use"}
        ) as stream:
            body = "".join(stream.iter_text())
        assert "token.delta" in body
        assert "stream.end" in body


def test_chat_session_history(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "v2.sqlite", corpus_root=_corpus(tmp_path))
    with TestClient(app) as client:
        first = client.post("/api/v2/chat", json={"topic_id": "agents", "message": "tool use"})
        assert first.status_code == 200
        session_id = first.json()["session_id"]
        second = client.post(
            "/api/v2/chat",
            json={"topic_id": "agents", "message": "tool use again", "session_id": session_id},
        )
        assert second.json()["session_id"] == session_id
        history = client.get(f"/api/v2/chat/sessions/{session_id}")
        assert len(history.json()["messages"]) == 4


def test_llm_composer_is_used(tmp_path: Path) -> None:
    def composer(question, citations):  # noqa: ANN001
        return f"LLM answer for {question} with {len(citations)} citations"

    app = create_app(
        db_path=tmp_path / "v2.sqlite",
        corpus_root=_corpus(tmp_path),
        chat_composer=composer,
    )
    with TestClient(app) as client:
        response = client.post("/api/v2/chat", json={"topic_id": "agents", "message": "tool use"})
        assert response.json()["text"].startswith("LLM answer")
