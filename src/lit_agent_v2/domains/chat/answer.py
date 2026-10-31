"""V2 chat domain."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.kernel.loop import Goal, Kernel, ToolBox

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
        state: dict[str, Any] = {}

        def search(_args: dict[str, Any]) -> dict[str, Any]:
            return {
                "paper_ids": [paper.paper_id for paper in ranked],
                "snippets": [
                    {"paper_id": paper.paper_id, "snippet": (paper.fulltext or paper.abstract)[:400]}
                    for paper in ranked
                ],
            }

        def verify(args: dict[str, Any]) -> dict[str, Any]:
            snippet = str(args.get("snippet") or "")
            return {"supported": bool(snippet), "coverage": 1.0 if snippet else 0.0}

        toolbox = ToolBox()
        toolbox.register("search_topic", search)
        toolbox.register("verify_claim", verify)

        def completer(history: list[dict[str, Any]]) -> dict[str, Any]:
            if not history:
                return {"action": "tool", "tool": "search_topic", "args": {}}
            output = history[0].get("output") or {}
            snippets = output.get("snippets") or []
            if not snippets:
                return {"action": "final", "outputs": {"answered": False, "reason": "no_evidence"}}
            if len(history) == 1:
                return {
                    "action": "tool",
                    "tool": "verify_claim",
                    "args": {"snippet": snippets[0]["snippet"]},
                }
            state["snippets"] = snippets
            return {"action": "final", "outputs": {"answered": True, "reason": ""}}

        result = Kernel().run(Goal(node_id="chat", objective=message), toolbox, completer)
        if not result.output.get("answered"):
            return ChatReply(
                text="I can't answer from this topic's evidence.",
                answered=False,
                reason=str(result.output.get("reason") or "failed"),
                trace=result.steps,
            )
        snippets = state.get("snippets") or []
        citations = [
            {"paper_id": item["paper_id"], "snippet": item["snippet"][:240]}
            for item in snippets[:3]
        ]
        text = f"According to [{citations[0]['paper_id']}]: {citations[0]['snippet']}"
        if self.composer is not None:
            composed = self.composer(message, citations)
            if composed:
                text = composed
        return ChatReply(text=text, citations=citations, answered=True, trace=result.steps)


def stream_reply(reply: ChatReply) -> list[dict[str, Any]]:
    """Deterministic token chunks; API can turn each into token.delta."""
    words = reply.text.split(" ")
    return [
        {"event": "token.delta", "delta": (" " if index else "") + word}
        for index, word in enumerate(words)
    ]
