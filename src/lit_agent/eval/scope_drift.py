"""漂移检测（S4，2.1-e 的产出者）：scope 与产出之间的覆盖率。

只做**确定性词面**判定（LLM 语义判定留给 Phase 3 的可选工具）：
- scope 少于 `MIN_SCOPE_TOKENS` 个有效 token → 无法判定（返回 ok），避免误报；
- `coverage < block_below` → block（真跑题）；
- `coverage < warn_below` → warn；
- 否则 ok。

"没有证据"不算漂移：本函数只比较"scope ↔ 产出"，空产出返回 ok。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["MIN_SCOPE_TOKENS", "DriftResult", "drift_for", "tokens"]

MIN_SCOPE_TOKENS = 2


def tokens(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


@dataclass(frozen=True)
class DriftResult:
    verdict: str  # ok | warn | block
    coverage: float
    scope_tokens: int

    @property
    def warning(self) -> bool:
        return self.verdict == "warn"

    @property
    def blocked(self) -> bool:
        return self.verdict == "block"


def drift_for(
    scope: str,
    claims: list[str],
    *,
    warn_below: float = 0.15,
    block_below: float = 0.05,
) -> DriftResult:
    scope_tokens = tokens(scope)
    if len(scope_tokens) < MIN_SCOPE_TOKENS:
        return DriftResult(verdict="ok", coverage=1.0, scope_tokens=len(scope_tokens))
    if not claims:
        return DriftResult(verdict="ok", coverage=1.0, scope_tokens=len(scope_tokens))

    produced = tokens(" ".join(claims))
    coverage = len(scope_tokens & produced) / len(scope_tokens)
    if coverage < block_below:
        verdict = "block"
    elif coverage < warn_below:
        verdict = "warn"
    else:
        verdict = "ok"
    return DriftResult(verdict=verdict, coverage=round(coverage, 4), scope_tokens=len(scope_tokens))
