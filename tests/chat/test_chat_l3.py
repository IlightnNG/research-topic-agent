"""3.3 / S13–S14 验收：Chat L3（会话持久化 + 无引用不作答）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lit_agent.agents.chat import answer
from lit_agent.api.app import create_app
from tests.wiring import prepare


def test_answers_with_citation(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = answer(settings, topic_id="ai-agents", message="tool use")

    assert reply.answered is True
    assert reply.citations
    assert reply.text.startswith("According to [P")
    assert any(item["tool"] == "search_topic" for item in reply.trace)


def test_refuses_without_evidence(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = answer(settings, topic_id="ai-agents", message="zzz-nonexistent")

    assert reply.answered is False
    assert reply.citations == []


def test_followup_keeps_session(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    app = create_app(settings)
    with TestClient(app) as client:
        first = client.post("/api/topics/ai-agents/chat", json={"message": "tool use"})
        assert first.status_code == 200, first.text
        session = first.json()["session_id"]
        assert first.json()["answered"] is True

        second = client.post(
            "/api/topics/ai-agents/chat",
            json={"message": "再具体一点", "session_id": session},
        )
        assert second.status_code == 200, second.text
        assert second.json()["session_id"] == session

        history = client.get("/api/topics/ai-agents/chat", params={"session_id": session})
        assert history.status_code == 200
        payload = history.json()
        assert len(payload["messages"]) == 4
        assert [item["role"] for item in payload["messages"]] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]
        assert payload["messages"][1]["citations"]


def test_unknown_topic_is_404(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/topics/nope/chat")
    assert response.status_code == 404


def test_refusal_is_persisted(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=0)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/topics/ai-agents/chat", json={"message": "anything"})
    assert response.status_code == 200
    assert response.json()["answered"] is False
    assert response.json()["message"]["citations"] == []


def test_new_session_is_empty(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=1)
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/topics/ai-agents/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        history = client.get("/api/topics/ai-agents/chat", params={"session_id": session_id})
        assert history.status_code == 200
        assert history.json()["session"]["id"] == session_id
        assert history.json()["messages"] == []


def test_chinese_query_hits_english_evidence(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    reply = answer(settings, topic_id="ai-agents", message="工具使用")
    assert reply.answered is True
    assert reply.citations


def test_unknown_session_is_404(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/topics/ai-agents/chat", params={"session_id": "chat-nope"})
    assert response.status_code == 404


def test_sessions_are_isolated(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/topics/ai-agents/chat", json={"message": "tool use"}).json()
        second_id = client.post("/api/topics/ai-agents/chat/sessions").json()["session_id"]
        second = client.post(
            "/api/topics/ai-agents/chat",
            json={"message": "zzz-nonexistent", "session_id": second_id},
        ).json()
        assert first["session_id"] != second["session_id"]

        one = client.get("/api/topics/ai-agents/chat", params={"session_id": first["session_id"]}).json()
        two = client.get("/api/topics/ai-agents/chat", params={"session_id": second["session_id"]}).json()
        assert len(one["messages"]) == 2
        assert len(two["messages"]) == 2
        assert one["messages"][0]["content"] != two["messages"][0]["content"]


class FakeGateway:
    def __init__(self, payload: dict | None = None, *, fail: bool = False) -> None:
        self.payload = payload or {"query": "tool use"}
        self.fail = fail

    def chat_json(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("gateway down")
        return self.payload, None

    def close(self) -> None:
        return None


def test_session_list_has_preview(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    with TestClient(create_app(settings)) as client:
        client.post("/api/topics/ai-agents/chat", json={"message": "tool use"})
        sessions = client.get("/api/topics/ai-agents/chat").json()["sessions"]

    assert sessions
    assert sessions[0]["preview"] == "tool use"
    assert sessions[0]["last_message_at"] is not None


def test_llm_rewrite_is_used(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = answer(
        settings,
        topic_id="ai-agents",
        message="工具使用",
        gateway=FakeGateway(),
    )

    assert reply.llm_used is True
    assert any(item["tool"] == "llm_rewrite" and item["ok"] for item in reply.trace)
    assert reply.answered is True


def test_llm_failure_falls_back(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = answer(
        settings,
        topic_id="ai-agents",
        message="工具使用",
        gateway=FakeGateway(fail=True),
    )

    assert reply.llm_used is False
    assert reply.answered is True
    assert any(item["tool"] == "llm_rewrite" and not item["ok"] for item in reply.trace)


def test_short_query_after_history_does_not_reuse_previous_question(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    history = [
        {"role": "user", "content": "tool use"},
        {"role": "assistant", "content": "According to [P0]: tool use improves..."},
    ]
    reply = answer(settings, topic_id="ai-agents", message="zzz-nonexistent", history=history)
    assert reply.answered is False
    assert reply.reason == "no_evidence"
