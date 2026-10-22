"""门禁（S2）：判"产物对不对"，不判"过程偏没偏"。

六类（冻结）：schema / evidence_sufficiency / citation_integrity / support_ratio / budget / drift。
- 只读 patch + state + ctx，不写库；
- 失败返回 `ok=False` 的 `GateResult`，由 supervisor 决定动作；
- 零值型门禁必须区分"没跑"与"跑了但为 0"（Phase 1 教训）。
"""

from __future__ import annotations

import json
from typing import Any

from lit_agent.contracts.nodeio import GateResult, NodeOutput
from lit_agent.runtime.context import RunContext

__all__ = ["GATE_NAMES", "run_gates"]

GATE_NAMES = (
    "schema",
    "evidence_sufficiency",
    "citation_integrity",
    "support_ratio",
    "budget",
    "drift",
)

MAX_OUTPUT_BYTES = 8 * 1024
MIN_SUPPORT_RATIO = 0.6


def _fail(name: str, code: str, action: str, reason: str, **details: Any) -> GateResult:
    return GateResult(
        name=name,
        ok=False,
        code=code,
        action=action,  # type: ignore[arg-type]
        reasons=[reason],
        details=details,
    )


def _claims(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = str((state.get("artifacts") or {}).get("claims_json") or "[]")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def gate_schema(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    try:
        NodeOutput.model_validate(patch)
    except Exception as exc:  # noqa: BLE001 - 校验失败即失败
        return _fail("schema", "E_SCHEMA_STAGE_OUTPUT", "retry", f"输出不符合 NodeOutput：{exc}")
    # `claims_json` 由 MAX_CLAIMS 限长且被引用门禁校验，不计入"大字段"判定
    artifacts = {
        key: value
        for key, value in (patch.get("artifacts") or {}).items()
        if key != "claims_json"
    }
    size = len(
        json.dumps(
            {"artifacts": artifacts, "counters": patch.get("counters")},
            ensure_ascii=False,
            default=str,
        )
    )
    if size > MAX_OUTPUT_BYTES:
        return _fail(
            "schema",
            "E_SCHEMA_STAGE_OUTPUT",
            "retry",
            f"输出过大（{size} B > {MAX_OUTPUT_BYTES} B）：正文应只放引用",
        )
    return None


def gate_evidence_sufficiency(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if stage != "retrieval":
        return None
    counters = patch.get("counters") or {}
    if "selected" not in counters:
        return None
    if int(counters.get("selected", 0)) > 0:
        return None
    return _fail(
        "evidence_sufficiency",
        "E_GROUND_NO_EVIDENCE",
        "repair",
        "本轮没有可用证据：应先扩大检索，而不是直接成文",
        selected=0,
        repair_target="retrieval",
    )


def gate_citation_integrity(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if stage != "report":
        return None
    claims = _claims(state)
    bad = [
        index
        for index, claim in enumerate(claims)
        if not claim.get("citations")
    ]
    if not bad:
        return None
    return _fail(
        "citation_integrity",
        "E_GROUND_UNRESOLVED_CITATION",
        "repair",
        f"{len(bad)} 条 claim 缺引用（index={bad[:5]}）",
        bad_indexes=bad,
    )


def gate_support_ratio(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if stage not in {"critique", "report"}:
        return None
    claims = _claims(state)
    if not claims:
        return None
    supported = sum(1 for claim in claims if claim.get("support") == "supported")
    ratio = supported / len(claims)
    if ratio >= MIN_SUPPORT_RATIO:
        return None
    return _fail(
        "support_ratio",
        "E_GROUND_UNSUPPORTED_RATIO",
        "degrade",
        f"supported 比例 {ratio:.2f} < {MIN_SUPPORT_RATIO}",
        ratio=round(ratio, 4),
    )


def gate_budget(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if ctx.budget.check() != "stop":
        return None
    return _fail(
        "budget",
        "E_BUDGET_EXCEEDED",
        "abort",
        f"预算已达上限：{ctx.budget.snapshot()['ratios']}",
        snapshot=ctx.budget.snapshot(),
    )


def gate_drift(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    counters = patch.get("counters") or {}
    if int(counters.get("drift_block", 0)) > 0:
        return _fail("drift", "E_GUARD_DRIFT", "abort", "范围漂移阻断")
    if int(counters.get("drift_warn", 0)) > 0:
        return GateResult(
            name="drift",
            ok=True,
            code="E_GUARD_DRIFT",
            action="annotate",
            reasons=["范围漂移告警：建议补充 scope 提示"],
        )
    return None


def run_gates(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> list[GateResult]:
    """跑全部门禁，只返回"非 continue"的判决（失败或 annotate）。"""
    results: list[GateResult] = []
    for gate in (
        gate_schema,
        gate_evidence_sufficiency,
        gate_citation_integrity,
        gate_support_ratio,
        gate_budget,
        gate_drift,
    ):
        try:
            verdict = gate(stage, patch, state, ctx)
        except Exception as exc:  # noqa: BLE001 - 门禁自身异常按失败处理
            verdict = _fail(gate.__name__, "E_UNEXPECTED", "retry", f"门禁异常：{exc}")
        if verdict is not None and (not verdict.ok or verdict.action != "continue"):
            results.append(verdict)
    return results
