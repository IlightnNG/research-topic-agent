"""3.4 / S7: independent verifier and workflow rejection."""

from __future__ import annotations

from lit_agent.workflow.spec import NodeSpec
from lit_agent.workflow.verifier import AgentVerifier


class FakeGateway:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        return {"verdict": self.verdict, "reasons": ["contract"]}, None


def test_agent_verifier_accepts() -> None:
    node = NodeSpec(id="report", kind="agent", goal="write", allowed_tools=("x",))
    verdict = AgentVerifier(FakeGateway("accept")).verify(node, {"text": "x"}, {})
    assert verdict.accept is True


def test_agent_verifier_rejects_and_repairs() -> None:
    node = NodeSpec(id="report", kind="agent", goal="write", allowed_tools=("x",))
    verdict = AgentVerifier(FakeGateway("repair")).verify(node, {"text": "x"}, {})
    assert verdict.accept is False
    assert verdict.repair is True
    assert "contract" in verdict.reasons
