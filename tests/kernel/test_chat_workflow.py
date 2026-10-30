"""3.4 / S8: ChatWorkflow shares kernel/tools with Report."""

from __future__ import annotations

from pathlib import Path

from lit_agent.workflow.chat import ChatWorkflow
from tests.wiring import prepare


def test_chat_workflow_answers_with_citation(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = ChatWorkflow(settings).run(topic_id="ai-agents", message="tool use")

    assert reply.answered is True
    assert reply.citations
    assert reply.text.startswith("According to [P")
    assert any(item.get("tool") == "search_topic" for item in reply.trace)


def test_chat_workflow_refuses_without_evidence(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    reply = ChatWorkflow(settings).run(topic_id="ai-agents", message="zzz-nonexistent")

    assert reply.answered is False
    assert reply.citations == []
    assert "can't answer" in reply.text or "无法" in reply.text
