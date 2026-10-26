"""Chat L3（3.3）：单 Goal 的 ReAct 循环 + 工具白名单 + 无引用不作答。

"薄壳"的极端形态：没有阶段，只有一个 Goal（回答用户问题）；
工具：rewrite_query → search_topic → verify_claim；答案必须带引用。
"""

from __future__ import annotations

import re
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
    reason: str = ""
    llm_used: bool = False


def _cards(settings: Settings, topic_id: str) -> list[Any]:
    from lit_agent.graph.nodes import Phase2Nodes

    node = Phase2Nodes(settings)
    node._topic_id = topic_id
    return node._cards()


_BILINGUAL = {
    "工具": "tool",
    "使用": "use",
    "智能体": "agent",
    "代理": "agent",
    "检索": "retrieval",
    "引用": "citation",
    "评估": "evaluation",
    "记忆": "memory",
    "规划": "planning",
    "上下文": "context",
    "压缩": "compression",
}


_CJK = re.compile(r"[\u4e00-\u9fff]")


def _reply_lang(message: str) -> str:
    """English by default; mirror Chinese questions; explicit request wins."""
    lower = message.lower()
    if any(marker in lower for marker in ("in english", "用英文", "english answer")):
        return "en"
    if any(marker in lower for marker in ("in chinese", "用中文", "中文回答")):
        return "zh"
    return "zh" if _CJK.search(message) else "en"


def _expand(query: str) -> str:
    """无 LLM 时的最小中英桥接：把常见中文术语替换为英文检索词。"""
    expanded = query
    for zh, en in _BILINGUAL.items():
        if zh in expanded:
            expanded = expanded.replace(zh, f" {en} ")
    return " ".join(expanded.split())


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
    gateway: Any | None = None,
) -> ChatReply:
    cards = _cards(settings, topic_id)
    history = history or []

    reply_lang = _reply_lang(message)
    query = _expand(message.strip())
    last_user = next(
        (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
        "",
    )
    followup_markers = ("再", "继续", "为什么", "具体", "more", "why", "details", "continue")
    if (
        len(query.split()) <= 1
        and last_user
        and any(marker in message.lower() for marker in followup_markers)
    ):
        query = f"{last_user} {query}".strip()

    selected: list[Any] = []
    trace: list[dict[str, Any]] = []
    llm_used = False

    if gateway is not None:
        try:
            payload, _call = gateway.chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite the user question into short English search keywords. "
                            'Return JSON: {"query": str}. Do not answer the question.'
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=80,
                agent="chat",
            )
            rewritten = str(payload.get("query") or "").strip() if isinstance(payload, dict) else ""
            if rewritten:
                query = f"{query} {rewritten}".strip()
                llm_used = True
                trace.append({"tool": "llm_rewrite", "ok": True})
        except Exception:  # noqa: BLE001 - LLM 失败必须回落确定性检索
            trace.append({"tool": "llm_rewrite", "ok": False})

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
            text=(
                "无法从本 topic 的证据回答这个问题（没有命中可引用的片段）。"
                if reply_lang == "zh"
                else "I can't answer from this topic's evidence: no citable snippets matched."
            ),
            citations=[],
            trace=trace,
            answered=False,
            reason="no_evidence",
            llm_used=llm_used,
        )

    top = selected[0]
    if not _supported(top.snippet, top.snippet):
        return ChatReply(
            text=(
                "命中的片段不足以验证回答，已拒答。"
                if reply_lang == "zh"
                else "The matched snippets are insufficient to verify an answer."
            ),
            citations=[],
            trace=trace,
            answered=False,
            reason="unsupported",
            llm_used=llm_used,
        )

    citations = [
        {"paper_id": card.paper_id, "snippet": card.snippet[:240]} for card in selected
    ]
    return ChatReply(
        text=(
            f"根据 [{citations[0]['paper_id']}]：{citations[0]['snippet']}"
            if reply_lang == "zh"
            else f"According to [{citations[0]['paper_id']}]: {citations[0]['snippet']}"
        ),
        citations=citations,
        trace=trace,
        answered=True,
        llm_used=llm_used,
    )
