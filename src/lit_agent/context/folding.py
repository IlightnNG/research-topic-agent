"""上下文折叠策略（guide §8）。

Phase 1 只有 `truncate`；`summarize` / `hierarchical` 显式未实现（P3 实现，
并需要"折叠后质量不劣化"的对照评测，见 guide §14-P3）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from lit_agent.context.budget import FitResult, fit_many
from lit_agent.errors import E_FEATURE_DISABLED, LitError

__all__ = ["FoldingStrategy", "TruncateFolding", "folding_for"]


class FoldingStrategy(Protocol):
    name: str

    def fold(self, texts: Sequence[str], *, budget_tokens: int) -> FitResult: ...


@dataclass
class TruncateFolding:
    """按预算逐个填充，超出即截断（最保守、可复现）。"""

    name: str = "truncate"

    def fold(self, texts: Sequence[str], *, budget_tokens: int) -> FitResult:
        return fit_many(list(texts), budget_tokens=budget_tokens)


def folding_for(strategy: str) -> FoldingStrategy:
    if strategy == "truncate":
        return TruncateFolding()
    raise LitError(
        E_FEATURE_DISABLED,
        f"折叠策略 {strategy!r} 在 Phase 3 实现（P3 需先做质量对照评测）",
        context={"strategy": strategy},
    )


def _unused(_: Any) -> None:  # pragma: no cover
    return None
