"""Chat as a fixed one-node workflow (Phase 3.4 / S8)."""

from __future__ import annotations

from typing import Any

from lit_agent.agents.chat import ChatReply, _expand, _reply_lang
from lit_agent.config import Settings
from lit_agent.kernel.runtime import Kernel
from lit_agent.kernel.tools import KernelTools
from lit_agent.workflow.runner import WorkflowRunner
from lit_agent.workflow.spec import NodeSpec, WorkflowSpec

__all__ = ["ChatWorkflow"]


class ChatWorkflow:
    """Node 'answer' calls the shared kernel with search + verify tools."""

    def __init__(self, settings: Settings, *, gateway: Any | None = None) -> None:
        self.settings = settings
        self.gateway = gateway

    def run(self, *, topic_id: str, message: str, history: list[dict[str, Any]] | None = None) -> ChatReply:
        from lit_agent.agents.chat import _cards

        cards = _cards(self.settings, topic_id)
        tools = KernelTools.from_cards(cards)
        reply_lang = _reply_lang(message)
        query = _expand(message.strip())
        previous = next(
            (str(item.get("content") or "") for item in reversed(history or []) if item.get("role") == "user"),
            "",
        )
        if len(query.split()) <= 1 and previous and any(
            marker in message.lower() for marker in ("再", "继续", "为什么", "具体", "more", "why", "details", "continue")
        ):
            query = f"{previous} {query}".strip()

        llm_used = False
        if self.gateway is not None:
            try:
                payload, _ = self.gateway.chat_json(
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
            except Exception:  # noqa: BLE001 - fall back to deterministic search
                pass

        state: dict[str, Any] = {"search": None, "verify": None}

        def completer(trace: list[dict[str, Any]], _goal: Any) -> dict[str, Any]:
            for item in trace:
                if item.get("tool") == "search_topic":
                    state["search"] = item.get("output")
                if item.get("tool") == "verify_claim":
                    state["verify"] = item.get("output")
            if state["search"] is None:
                return {"action": "tool", "tool": "search_topic", "args": {"query": query, "k": 3}}
            snippets = list((state["search"] or {}).get("snippets") or [])
            if not snippets:
                return {"action": "final", "outputs": self._refusal(reply_lang, "no_evidence")}
            if state["verify"] is None:
                return {
                    "action": "tool",
                    "tool": "verify_claim",
                    "args": {"text": snippets[0]["snippet"], "snippet": snippets[0]["snippet"]},
                }
            supported = bool((state["verify"] or {}).get("supported"))
            if not supported:
                return {"action": "final", "outputs": self._refusal(reply_lang, "unsupported")}
            citations = [
                {"paper_id": item["paper_id"], "snippet": item["snippet"][:240]}
                for item in snippets
            ]
            text = (
                f"根据 [{citations[0]['paper_id']}]：{citations[0]['snippet']}"
                if reply_lang == "zh"
                else f"According to [{citations[0]['paper_id']}]: {citations[0]['snippet']}"
            )
            return {
                "action": "final",
                "outputs": {
                    "text": text,
                    "citations": citations,
                    "answered": True,
                    "reason": "",
                    "trace": [
                        {"tool": "search_topic", "ok": True, "hits": len(snippets)},
                        {"tool": "verify_claim", "ok": True},
                        {"tool": "workflow", "ok": True},
                    ],
                },
            }

        spec = WorkflowSpec(
            name="chat",
            nodes=(
                NodeSpec(
                    id="answer",
                    kind="agent",
                    goal="answer from topic evidence or refuse",
                    output_key="reply",
                    allowed_tools=("search_topic", "verify_claim"),
                    postconditions=("text", "citations", "answered"),
                    budget_usd=0.05,
                    timeout_s=60.0,
                ),
            ),
        )
        runner = WorkflowRunner(
            spec,
            kernel=Kernel(tools=tools, gateway=self.gateway),
            completers={"answer": completer},
        )
        result = runner.run()
        payload = result.artifacts.get("reply")
        if result.failed_node or not isinstance(payload, dict):
            return ChatReply(
                text="Chat workflow failed; no answer was produced.",
                answered=False,
                reason="failed",
                trace=[],
            )
        return ChatReply(
            text=str(payload.get("text") or ""),
            citations=list(payload.get("citations") or []),
            trace=list(payload.get("trace") or []),
            answered=bool(payload.get("answered")),
            reason=str(payload.get("reason") or ""),
            llm_used=llm_used,
        )

    @staticmethod
    def _refusal(language: str, reason: str) -> dict[str, Any]:
        if language == "zh":
            text = (
                "无法从本 topic 的证据回答这个问题（没有命中可引用的片段）。"
                if reason == "no_evidence"
                else "命中的片段不足以验证回答，已拒答。"
            )
        else:
            text = (
                "I can't answer from this topic's evidence: no citable snippets matched."
                if reason == "no_evidence"
                else "The matched snippets are insufficient to verify an answer."
            )
        return {
            "text": text,
            "citations": [],
            "answered": False,
            "reason": reason,
            "trace": [{"tool": "workflow", "ok": True}],
        }
