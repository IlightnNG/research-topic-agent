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
    "llm_calls",
    "drift",
    "report_contract",
)

MAX_OUTPUT_BYTES = 8 * 1024
MIN_SUPPORT_RATIO = 0.6  # 默认值；运行时以 ctx.pipeline.gates.support_ratio_min 为准


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
        if key not in {"claims_json", "report_draft_json", "report_cards_json"}
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
    min_cards = int(getattr(ctx.gates_cfg, "evidence_min_cards", 1))
    selected = int(counters.get("selected", 0))
    if selected >= min_cards:
        return None
    return _fail(
        "evidence_sufficiency",
        "E_GROUND_NO_EVIDENCE",
        "repair",
        f"证据不足：选中 {selected} 篇 < 要求 {min_cards} 篇",
        selected=selected,
        min_cards=min_cards,
        repair_target="retrieval",
    )


def gate_citation_integrity(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if stage not in {"critique", "report"}:
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
        repair_target="analysis",
    )


def gate_support_ratio(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    if stage != "critique":
        return None
    claims = _claims(state)
    if not claims:
        return None
    supported = sum(1 for claim in claims if claim.get("support") == "supported")
    ratio = supported / len(claims)
    min_ratio = float(getattr(ctx.gates_cfg, "support_ratio_min", MIN_SUPPORT_RATIO))
    if ratio >= min_ratio:
        return None
    return _fail(
        "support_ratio",
        "E_GROUND_UNSUPPORTED_RATIO",
        "repair",
        f"supported 比例 {ratio:.2f} < {min_ratio}：尝试补一次证据/重写",
        ratio=round(ratio, 4),
        min_ratio=min_ratio,
        repair_target="analysis",
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


def gate_llm_calls(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    """单 run 的 LLM 调用数硬顶（S2）：DB 计数，不依赖内存。"""
    limit = int(getattr(ctx.limits_cfg, "max_total_llm_calls", 12))
    from sqlalchemy import text as _text

    from lit_agent.db.session import connect

    with connect(ctx.engine) as conn:
        used = int(
            conn.execute(
                _text("SELECT COUNT(*) FROM llm_calls WHERE run_id = :rid"),
                {"rid": ctx.run_id},
            ).scalar_one()
        )
    if used < limit:
        return None
    return _fail(
        "llm_calls",
        "E_BUDGET_EXCEEDED",
        "abort",
        f"LLM 调用数已达上限（{used}/{limit}）",
        llm_calls_used=used,
        limit=limit,
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


def gate_report_contract(
    stage: str, patch: dict[str, Any], state: dict[str, Any], ctx: RunContext
) -> GateResult | None:
    """v2 draft 的结构/引用校验；旧报告（无 draft）跳过。"""
    if stage != "report":
        return None
    draft = (patch.get("artifacts") or {}).get("report_draft_json")
    if not draft:
        return None
    from lit_agent.models.report import Report
    from lit_agent.report.assemble import validate_report

    try:
        report = Report.model_validate(draft)
        verdict = validate_report(report, language=report.language)
    except Exception as exc:  # noqa: BLE001
        return _fail("report_contract", "E_REPORT_SCHEMA", "retry", f"报告 draft 非法：{exc}")
    if not verdict.ok:
        return _fail(
            "report_contract",
            "E_REPORT_SCHEMA",
            "retry",
            f"报告校验失败：{verdict.errors[:2]}",
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
        gate_llm_calls,
        gate_drift,
        gate_report_contract,
    ):
        try:
            verdict = gate(stage, patch, state, ctx)
        except Exception as exc:  # noqa: BLE001 - 门禁自身异常按失败处理
            verdict = _fail(gate.__name__, "E_UNEXPECTED", "retry", f"门禁异常：{exc}")
        if verdict is not None and (not verdict.ok or verdict.action != "continue"):
            results.append(verdict)
    return results
