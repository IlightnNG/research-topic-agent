"""Kernel tool registry (Phase 3.4 / S2).

Every capability the kernel can call is a ToolSpec with schema, timeout and an
explicit side-effect contract. Domain tools are thin wrappers around existing
implementations; no workflow planning lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lit_agent.agents.hybrid import hybrid_search
from lit_agent.kernel.events import EventSink, emit
from lit_agent.models.evidence import EvidenceCard
from lit_agent.tools.spec import (
    DEFAULT_TOOL_SPECS,
    TOOL_IMPLEMENTATIONS,
    ToolRuntime,
    ToolSpec,
)

__all__ = ["KernelTools", "register_core_tools"]


def _search_topic(cards: list[EvidenceCard], query: str, k: int = 5) -> dict[str, Any]:
    result = hybrid_search(cards, query, k=max(1, min(int(k), 20)), alpha=0.6, min_score=0.15)
    selected = list(result.cards)
    return {
        "paper_ids": [card.paper_id for card in selected],
        "count": len(selected),
        "snippets": [{"paper_id": card.paper_id, "snippet": card.snippet} for card in selected],
    }


def register_core_tools(runtime: ToolRuntime, cards: list[EvidenceCard]) -> None:
    """Register the safe read-only tools a node may use."""
    for name in ("rewrite_query", "verify_claim", "extract_claims", "compress_context"):
        runtime.register(DEFAULT_TOOL_SPECS[name], TOOL_IMPLEMENTATIONS[name])
    runtime.register(
        ToolSpec(
            name="search_topic",
            description="Hybrid search over the topic's evidence cards",
            parameters={"query": "string", "k": "number"},
            output_schema={
                "type": "object",
                "required": ["paper_ids", "count"],
            },
            timeout_s=10.0,
        ),
        lambda **kwargs: _search_topic(
            cards, str(kwargs.get("query") or ""), int(kwargs.get("k") or 5)
        ),
    )


@dataclass
class KernelTools:
    runtime: ToolRuntime
    event_sink: EventSink | None = None

    @classmethod
    def from_cards(
        cls, cards: list[EvidenceCard], *, event_sink: EventSink | None = None
    ) -> KernelTools:
        runtime = ToolRuntime()
        register_core_tools(runtime, cards)
        return cls(runtime=runtime, event_sink=event_sink)

    def names(self) -> list[str]:
        return self.runtime.names()

    def spec(self, name: str) -> ToolSpec:
        return self.runtime.spec(name)

    def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        emit(self.event_sink, "tool.called", tool=name, args=args or {})
        result = self.runtime.call(name, args=args or {})
        emit(
            self.event_sink,
            "tool.result",
            tool=name,
            ok=result.ok,
            error_code=result.error_code,
        )
        return result
