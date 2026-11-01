"""Ports for the Node Platform kernel."""

from __future__ import annotations

from typing import Any, Protocol

from lit_agent_v2.contracts.tool import ToolResult, ToolSpec

__all__ = ["CheckpointPort", "EventPort", "LLMPort", "ToolRegistryPort"]


class LLMPort(Protocol):
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        prompt_version: str = "node-v1",
        max_tokens: int = 4000,
        temperature: float = 0.1,
    ) -> tuple[dict, Any]: ...


class ToolRegistryPort(Protocol):
    def names(self) -> list[str]: ...
    def spec(self, name: str) -> ToolSpec | None: ...
    def call(self, name: str, args: dict[str, Any]) -> ToolResult: ...


class CheckpointPort(Protocol):
    def save(self, run_id: str, node_id: str, checkpoint: dict[str, Any]) -> None: ...
    def load(self, run_id: str, node_id: str) -> dict[str, Any] | None: ...


class EventPort(Protocol):
    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> None: ...
