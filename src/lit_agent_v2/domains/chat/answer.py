"""V2 chat domain: local evidence retrieval with a deterministic answer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.research.corpus import LocalCorpus

__all__ = ["ChatReply", "ChatService", "stream_reply"]


@dataclass
class ChatReply:
    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    answered: bool = False
    reason: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)


def _tokens(text: str) -> set[str]:
    return {word for word in re.split(r"\W+", text.lower()) if len(word) > 2}


class ChatService:
    def __init__(self, corpus: LocalCorpus, *, composer=None) -> None:
        self.corpus = corpus
        self.composer = composer

    def answer(self, *, topic_id: str, message: str, limit: int = 5) -> ChatReply:
        papers = self.corpus.papers()
        wanted = _tokens(message)
        scored = [
            (
                len(wanted & _tokens(f"{paper.title} {paper.abstract} {paper.fulltext}")),
                paper,
            )
            for paper in papers
        ]
        scored.sort(key=lambda item: (-item[0], item[1].paper_id))
        ranked = [paper for score, paper in scored if score > 0][:limit]
        if not ranked:
            return ChatReply(
                text="I can't answer from this topic's evidence.",
                answered=False,
                reason="no_evidence",
            )
        citations = [
            {
                "paper_id": paper.paper_id,
                "snippet": (paper.fulltext or paper.abstract or paper.title)[:240],
            }
            for paper in ranked[:3]
        ]
        text = f"According to [{citations[0]['paper_id']}]: {citations[0]['snippet']}"
        if self.composer is not None:
            composed = self.composer(message, citations)
            if composed:
                text = composed
        return ChatReply(text=text, citations=citations, answered=True)


def stream_reply(reply: ChatReply) -> list[dict[str, Any]]:
    """Deterministic token chunks; API can turn each into token.delta."""
    words = reply.text.split(" ")
    return [
        {"event": "token.delta", "delta": (" " if index else "") + word}
        for index, word in enumerate(words)
    ]
