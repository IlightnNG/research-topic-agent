"""M5-P01: LLM judge schema and live call."""

from __future__ import annotations

import os

import pytest

from lit_agent_v2.evaluation.judge import JudgeError, LLMJudge


class FakeJudge:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        return self.payload, None


def test_judge_parses_rubric() -> None:
    judge = LLMJudge(
        FakeJudge(
            {
                "scores": {
                    "relevance": 4,
                    "coverage": 4,
                    "grounding": 5,
                    "synthesis": 3,
                    "readability": 4,
                    "actionability": 3,
                },
                "problems": [],
                "verdict": "accept",
            }
        )
    )
    result = judge.score("report [C1]", [{"paper_id": "P1", "text": "x"}])
    assert result.scores.grounding == 5
    assert result.verdict == "accept"


def test_judge_rejects_bad_score() -> None:
    judge = LLMJudge(FakeJudge({"scores": {"relevance": 9}}))
    with pytest.raises(JudgeError):
        judge.score("report", [])


@pytest.mark.skipif(os.environ.get("LIT_V2_LIVE") != "1", reason="set LIT_V2_LIVE=1 for live LLM")
def test_live_judge() -> None:
    from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config

    judge = LLMJudge(DeepSeekChatClient(load_llm_config()))
    result = judge.score(
        "Tool routing improves agent success on benchmark tasks [C1].",
        [{"paper_id": "P1", "text": "Tool routing improves agent success on benchmark tasks."}],
    )
    assert 1 <= result.scores.grounding <= 5
