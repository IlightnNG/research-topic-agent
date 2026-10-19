"""路由与敏感度硬门（guide §5）。

`strict` 模式下命中敏感模式 → **零出网**直接拒绝（`E_POLICY_SENSITIVE`），
不允许"先发出去再判断"。复杂度分流留 Phase 2（此处 route 恒为 cloud）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lit_agent.errors import E_FEATURE_DISABLED, E_POLICY_SENSITIVE, LitError

__all__ = ["Decision", "SENSITIVE_PATTERNS", "decide", "local_route", "messages_to_text"]

SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("api_key", re.compile(r"\b(sk-[A-Za-z0-9._-]{8,}|ghp_[A-Za-z0-9]{20,})\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential", re.compile(r"(?i)\b(password|passwd|secret|token)\s*[:=]\s*\S{6,}")),
)


@dataclass(frozen=True)
class Decision:
    route: str  # cloud | blocked
    reason: str


def messages_to_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(str(item.get("content", "")) for item in messages)


def decide(messages: list[dict[str, Any]], *, sensitivity: str = "strict") -> Decision:
    """返回路由决策；`strict` 命中敏感即抛错（调用方不得再发请求）。"""
    if sensitivity == "off":
        return Decision(route="cloud", reason="sensitivity:off")
    text = messages_to_text(messages)
    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            raise LitError(
                E_POLICY_SENSITIVE,
                f"敏感内容命中（{name}）：strict 模式下拒绝出网",
                context={"pattern": name, "sensitivity": sensitivity},
            )
    return Decision(route="cloud", reason=f"sensitivity:{sensitivity}")


def local_route() -> None:
    """Phase 1 不实现本地模型路由（Phase 2 的熔断/分流）。"""
    raise LitError(
        E_FEATURE_DISABLED, "local 模型路由在 Phase 2 实现", context={"feature": "gateway.local"}
    )
