"""计量与预算（guide §5 / §13）。

- 每次调用写一行 `llm_calls`（append-only；重试产生多行是正确的）；
- `usage` 缺失时按字符估算 token 并标记 `cost_estimated`（**禁止把成本静默记成 0**）；
- 预算两档：≥80% warn、≥100% stop。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

__all__ = ["BudgetGuard", "CallUsage", "estimate_tokens"]

WARN_RATIO = 0.8


@dataclass(frozen=True)
class CallUsage:
    req_tokens: int = 0
    resp_tokens: int = 0
    cost: float = 0.0
    estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.req_tokens + self.resp_tokens


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：CJK 按 1.5 字符/token、其余按 4 字符/token（仅 usage 缺失时兜底）。"""
    if not text:
        return 0
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = len(text) - cjk
    return max(1, int(math.ceil(cjk / 1.5 + latin / 4)))


class BudgetGuard:
    """美元预算（run 级）。`check()` 在**调用前**判定，`spend()` 在调用后累计。"""

    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = float(limit_usd)
        self.spent_usd = 0.0

    def check(self) -> str:
        if self.limit_usd <= 0:
            return "ok"
        ratio = self.spent_usd / self.limit_usd
        if ratio >= 1.0:
            return "stop"
        if ratio >= WARN_RATIO:
            return "warn"
        return "ok"

    def spend(self, usage: CallUsage) -> str:
        self.spent_usd += max(0.0, float(usage.cost))
        return self.check()

    def snapshot(self) -> dict[str, Any]:
        return {
            "limit_usd": self.limit_usd,
            "spent_usd": round(self.spent_usd, 6),
            "state": self.check(),
        }
