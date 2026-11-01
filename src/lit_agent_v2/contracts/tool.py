"""Tool contracts. No workflow/kernel/domain imports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ToolCall", "ToolResult", "ToolSpec"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    side_effect: bool = False
    idempotent: bool = True
    timeout_s: float = 30.0
    cost_usd: float = 0.0
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict[str, Any]
    call_id: str = ""


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    retryable: bool = False
    duration_ms: int = 0
    cost_usd: float = 0.0
