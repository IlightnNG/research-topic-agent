"""Chat L3（3.3）：单 Goal 的 ReAct 循环 + 工具白名单 + 无引用不作答。

"薄壳"的极端形态：没有阶段，只有一个 Goal（回答用户问题）；
工具：rewrite_query → search_topic → verify_claim；答案必须带引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lit_agent.config import Settings
from lit_agent.contracts.goals import NodeGoal
from lit_agent.runtime.micro_agent import MicroAgent
from lit_agent.tools.spec import ToolSpec, tool_runtime_for

__all__ = ["ChatReply", "CHAT_GOAL", "answer"]

CHAT_GOAL = NodeGoal(
    name="chat",
    objective="用 topic 内证据回答用户问题；没有引用就明确拒答",
    postconditions=("schema",),
    tools=("rewrite_query", "search_topic", "verify_claim"),
    max_steps=4,
    max_usd=0.05,
    autonomy="L3",
)


@dataclass
class ChatReply:
    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    answered: bool = False


def _cards(settings: Settings, topic_id: str) -> list[Any]:
    from lit_agent.graph.nodes import Phase2Nodes

    node = Phase2Nodes(settings)
    node._topic_id = topic_id
    return node._cards()


def _supported(text: str, snippet: str) -> bool:
    from lit_agent.eval.grounding import check_claim
    from lit_agent.models.claim import Claim
    from lit_agent.models.evidence import Citation

    if not snippet:
        return False
    result = check_claim(Claim(text=text, citations=[Citation(paper_id="chat", snippet=snippet)]))
    return bool(result.supported)


def answer(
    settings: Settings,
    *,
    topic_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> ChatReply:
    cards = _cards(settings, topic_id)
    history = history or []

    query = message.strip()
    last_user = next(
        (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
        "",
    )
    if len(query.split()) <= 1 and last_user:
        query = f"{last_user} {query}".strip()

    selected: list[Any] = []
    trace: list[dict[str, Any]] = []

    def search(*, query: str = "") -> dict[str, Any]:
        nonlocal selected
        from lit_agent.agents.hybrid import hybrid_search

        result = hybrid_search(cards, query or "", alpha=0.6, min_score=0.15)
        selected = list(result.cards)[:3]
        trace.append({"tool": "search_topic", "ok": True, "hits": len(selected)})
        return {"paper_ids": [card.paper_id for card in selected], "count": len(selected)}

    runtime = tool_runtime_for(("rewrite_query", "verify_claim"))
    runtime.register(
        ToolSpec(
            name="search_topic",
            description="在 topic 证据卡里检索",
            parameters={"query": "string"},
            output_schema={"type": "object", "required": ["paper_ids"]},
            concurrency="parallel",
        ),
        search,
    )

    actions: list[dict[str, Any]] = [
        {"action": "tool", "tool": "rewrite_query", "args": {"query": query}},
        {"action": "tool", "tool": "search_topic", "args": {"query": query}},
        {"action": "tool", "tool": "verify_claim", "args": {}},
        {"action": "final", "outputs": {}},
    ]

    def completer(messages: list[dict[str, str]], goal: NodeGoal) -> dict[str, Any]:
        if not actions:
            return {"action": "final", "outputs": {}}
        action = actions.pop(0)
        if action.get("tool") == "verify_claim":
            if not selected:
                return {"action": "final", "outputs": {}}
            top = selected[0]
            return {
                "action": "tool",
                "tool": "verify_claim",
                "args": {"text": top.snippet, "snippet": top.snippet},
            }
        return action

    agent = MicroAgent(completer=completer, tools=runtime, max_total_steps=5)
    result = agent.run(CHAT_GOAL)
    trace.append({"tool": "loop", "ok": True, "steps": result.steps_used, "stop": result.stop_reason})

    if not selected:
        return ChatReply(
            text="无法从本 topic 的证据回答这个问题（没有命中可引用的片段）。",
            citations=[],
            trace=trace,
            answered=False,
        )

    top = selected[0]
    if not _supported(top.snippet, top.snippet):
        return ChatReply(
            text="命中的片段不足以验证回答，已拒答。",
            citations=[],
            trace=trace,
            answered=False,
        )

    citations = [
        {"paper_id": card.paper_id, "snippet": card.snippet[:240]} for card in selected
    ]
    return ChatReply(
        text=f"根据 [{citations[0]['paper_id']}]：{citations[0]['snippet']}",
        citations=citations,
        trace=trace,
        answered=True,
    )
