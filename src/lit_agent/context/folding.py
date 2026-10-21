"""上下文折叠策略（S7）。

三档：
- `truncate`：按预算截断（Phase 1 已有，最保守）；
- `summarize`：**先剪枝后摘要**——每段只留前 N 句 + 含数字/引用的句子，再按预算填充；
- `hierarchical`：仍为显式未实现（需要分层摘要与质量对照评测，P3）。

约束：折叠**不得切断引用片段**——片段来自 `Citation.snippet`，本模块只处理正文，
引用片段由报告层单独保留。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from lit_agent.context.budget import FitResult, fit_many
from lit_agent.errors import E_FEATURE_DISABLED, LitError

__all__ = ["FoldingStrategy", "SummarizeFolding", "TruncateFolding", "folding_for"]


class FoldingStrategy(Protocol):
    name: str

    def fold(self, texts: Sequence[str], *, budget_tokens: int) -> FitResult: ...


@dataclass
class TruncateFolding:
    name: str = "truncate"

    def fold(self, texts: Sequence[str], *, budget_tokens: int) -> FitResult:
        return fit_many(list(texts), budget_tokens=budget_tokens)


@dataclass
class SummarizeFolding:
    """抽取式摘要：剪枝 + 选句，确定性、零 LLM 成本。"""

    name: str = "summarize"
    keep_sentences: int = 1

    def _sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
        return [part for part in parts if part]

    def prune(self, text: str) -> str:
        sentences = self._sentences(text)
        kept: list[str] = []
        for index, sentence in enumerate(sentences):
            if index < self.keep_sentences or re.search(r"\d{2,}|\[\d+\]", sentence):
                kept.append(sentence)
        return " ".join(kept) if kept else text[:400]

    def fold(self, texts: Sequence[str], *, budget_tokens: int) -> FitResult:
        pruned = [self.prune(text) for text in texts]
        return fit_many(pruned, budget_tokens=budget_tokens)


def folding_for(strategy: str) -> FoldingStrategy:
    if strategy == "truncate":
        return TruncateFolding()
    if strategy == "summarize":
        return SummarizeFolding()
    raise LitError(
        E_FEATURE_DISABLED,
        f"折叠策略 {strategy!r} 尚未实现（P3 需先做质量对照评测）",
        context={"strategy": strategy},
    )
