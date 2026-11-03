"""Tool contracts. No workflow/kernel/domain imports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ToolCall", "ToolContext", "ToolError", "ToolResult", "ToolSpec"]


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
    max_retries: int = 0
    retry_on: tuple[str, ...] = ("E_TOOL_TIMEOUT",)
    handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    context_handler: Callable[[dict[str, Any], ToolContext], dict[str, Any]] | None = None

    # Phase 4.2 metadata. Fields stay optional so existing packs remain valid.
    namespace: str = ""
    title: str = ""
    version: str = "1"
    parallel_safe: bool | None = None
    repeatable: bool = False
    requires_approval: bool = False
    max_output_chars: int = 20000
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    render: Callable[[dict[str, Any], dict[str, Any]], str] | None = None

    @property
    def effective_parallel_safe(self) -> bool:
        if self.parallel_safe is None:
            return not self.side_effect
        return self.parallel_safe


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict[str, Any]
    call_id: str = ""


@dataclass(frozen=True)
class ToolContext:
    run_id: str = ""
    node_id: str = ""
    call_id: str = ""
    workspace: str = ""
    signal: Callable[[], bool] | None = None
    events: Any = None
    artifacts: Any = None
    state: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str = ""
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    retryable: bool = False
    duration_ms: int = 0
    cost_usd: float = 0.0
    content: str = ""
    error: ToolError | None = None
    artifact_refs: list[str] = field(default_factory=list)
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
