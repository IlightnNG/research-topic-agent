"""Ports for verification."""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["AuditLLMPort"]


class AuditLLMPort(Protocol):
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str = "verify-v1",
        max_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> tuple[dict, Any]: ...
