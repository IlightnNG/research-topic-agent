"""批判 agent（S6）：对 claims 做结构自查，产出 `GuardVerdict` 形态的判决。

只做**可判定**的检查（不靠 LLM 自评）：缺引用 / 重复文本 / supported 比例过低 / 证据为空。
输出字段与 `models/verdict.py` 的 `GuardVerdict` 对齐，可直接被 runner 发成 `guard_trigger` 事件。
"""

from __future__ import annotations

from typing import Any

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Support
from lit_agent.models.verdict import GuardAction, GuardSeverity, Verdict

__all__ = ["critique", "run"]

MIN_SUPPORTED_RATIO = 0.6


def critique(claims: list[Claim]) -> Verdict:
    if not claims:
        return Verdict(
            ok=False,
            severity=GuardSeverity.WARN,
            action=GuardAction.DEGRADE,
            code="E_GROUND_NO_EVIDENCE",
            reasons=["没有可用证据（claims 为空）"],
        )

    missing = [index for index, claim in enumerate(claims) if not claim.citations]
    if missing:
        return Verdict(
            ok=False,
            severity=GuardSeverity.BLOCK,
            action=GuardAction.RETRY,
            code="E_GROUND_UNRESOLVED_CITATION",
            reasons=[f"{len(missing)} 条 claim 缺引用（index={missing[:5]}）"],
        )

    texts = [claim.text for claim in claims]
    duplicates = len(texts) - len(set(texts))
    supported = sum(1 for claim in claims if claim.support is Support.SUPPORTED)
    ratio = supported / len(claims)

    if duplicates:
        return Verdict(
            ok=False,
            severity=GuardSeverity.WARN,
            action=GuardAction.RETRY,
            code="E_SCHEMA_STAGE_OUTPUT",
            reasons=[f"{duplicates} 条 claim 文本重复"],
        )
    if ratio < MIN_SUPPORTED_RATIO:
        return Verdict(
            ok=False,
            severity=GuardSeverity.WARN,
            action=GuardAction.DEGRADE,
            code="E_GROUND_UNSUPPORTED_RATIO",
            reasons=[f"supported 比例 {ratio:.2f} < {MIN_SUPPORTED_RATIO}"],
        )
    return Verdict(
        ok=True,
        severity=GuardSeverity.INFO,
        action=GuardAction.CONTINUE,
        code="E_OK",
        reasons=[f"{len(claims)} 条 claim，全部带引用"],
    )


def run(state: dict[str, Any], *, claims: list[Claim] | None = None, **_: Any) -> dict[str, Any]:
    verdict = critique(claims or [])
    return {
        "artifacts": {"verdict": verdict.model_dump(mode="json")},
        "counters": {"critique_block": 0 if verdict.ok else 1},
    }
