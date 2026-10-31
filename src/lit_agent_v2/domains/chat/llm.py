"""V2 chat LLM adapter."""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["LLMChatClient"]


class LLMChatClient(Protocol):
    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> tuple[dict, Any]: ...


class GroundedChatLLM:
    def __init__(self, client: LLMChatClient) -> None:
        self.client = client

    def compose(self, question: str, snippets: list[dict[str, Any]]) -> str:
        material = "\n".join(
            f"[{item['paper_id']}] {item['snippet']}" for item in snippets[:3]
        )
        payload, _ = self.client.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer only from the provided snippets. If they do not answer, "
                        'say you cannot answer. Return JSON: {"text": str}.'
                    ),
                },
                {"role": "user", "content": f"Q: {question}\n\nSnippets:\n{material}"},
            ],
            max_tokens=300,
        )
        return str(payload.get("text") or "").strip()
