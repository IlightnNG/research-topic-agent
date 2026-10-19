"""token 预算与截断（guide §8）。

Phase 1 只做"按预算保留头部 + 句界截断"，**保证引用锚点不被切断**（Phase 0 教训）。
摘要/分层折叠在 P3 实现（`folding.py`）。
"""

from __future__ import annotations

from dataclasses import dataclass

from lit_agent.parsing.chunking import count_tokens

__all__ = ["FitResult", "fit_many", "fit_text"]


@dataclass(frozen=True)
class FitResult:
    text: str
    tokens: int
    truncated: bool


def _split_sentences(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [part for part in parts if part]


def fit_text(text: str, *, budget_tokens: int, min_tokens: int = 8) -> FitResult:
    """在预算内保留尽量多的完整句子；超预算才截断。"""
    if budget_tokens <= 0:
        raise ValueError("budget_tokens 必须为正")
    total = count_tokens(text)
    if total <= budget_tokens:
        return FitResult(text=text, tokens=total, truncated=False)

    kept: list[str] = []
    used = 0
    for sentence in _split_sentences(text):
        cost = count_tokens(sentence)
        if used + cost > budget_tokens:
            break
        kept.append(sentence)
        used += cost
    if not kept:
        # 单句就超预算：按字符硬切一个保守比例（避免返回空字符串）
        ratio = budget_tokens / max(1, total)
        head = text[: max(1, int(len(text) * ratio))]
        return FitResult(text=head, tokens=count_tokens(head), truncated=True)
    return FitResult(text=" ".join(kept), tokens=used, truncated=True)


def fit_many(texts: list[str], *, budget_tokens: int) -> FitResult:
    """按顺序填充预算，返回合并结果。"""
    kept: list[str] = []
    used = 0
    truncated = False
    for text in texts:
        remaining = budget_tokens - used
        if remaining <= 0:
            truncated = True
            break
        result = fit_text(text, budget_tokens=remaining)
        if result.text:
            kept.append(result.text)
            used += result.tokens
        truncated = truncated or result.truncated
    return FitResult(text="\n".join(kept), tokens=used, truncated=truncated)
