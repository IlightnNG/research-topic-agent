"""提交层（S2）：执行节点的 `pending_writes`。

- **只在门禁通过后调用**（两阶段提交）；
- 所有写入幂等（报告 insert_ignore、claims 同事务、指标 upsert）→ 重试/续跑安全；
- 支持 `drop_claim_indexes`：门禁判定缺引用的 claim 不落库（降级而非带病入库）。
"""

from __future__ import annotations

from typing import Any

from lit_agent.contracts.nodeio import Decision
from lit_agent.runtime.context import RunContext

__all__ = ["commit_pending"]


def _claims_from_state(state: dict[str, Any]) -> list[Any]:
    from lit_agent.agents.analyst import claims_from_json

    return claims_from_json(str((state.get("artifacts") or {}).get("claims_json") or "[]"))


def commit_pending(
    ctx: RunContext,
    state: dict[str, Any],
    patch: dict[str, Any],
    decision: Decision,
) -> dict[str, Any]:
    """执行声明的写入，返回提交摘要（进入事件 payload）。"""
    summary: dict[str, Any] = {}
    writes = patch.get("pending_writes") or []
    for write in writes:
        kind = str(write.get("kind") or "")
        if kind == "report":
            draft_payload = (patch.get("artifacts") or {}).get("report_draft_json")
            if draft_payload:
                from lit_agent.models.report import Report
                from lit_agent.runtime.runner import persist_report_draft

                draft = Report.model_validate(draft_payload)
                report_id = persist_report_draft(ctx.settings, ctx.run_id, draft)
                summary["report_id"] = report_id
                summary["claims_written"] = len(draft.claims)
                summary["dropped_claims"] = 0
                summary["report_generated_by"] = draft.generated_by
                summary["report_sections"] = len(draft.sections)
                summary["llm_used"] = draft.generated_by == "llm"
                summary["extraction"] = "llm" if draft.generated_by == "llm" else "deterministic"
                continue

            from lit_agent.runtime.runner import persist_report_from_claims

            claims = _claims_from_state(state)
            drop = {int(index) for index in (decision.drop_claim_indexes or [])}
            if drop:
                claims = [
                    claim for index, claim in enumerate(claims) if index not in drop
                ]
            report_id = persist_report_from_claims(
                ctx.settings,
                ctx.run_id,
                ctx.topic_id,
                claims,
                focus_hint=state.get("focus_hint"),
            )
            summary["report_id"] = report_id
            summary["claims_written"] = len(claims)
            summary["dropped_claims"] = len(drop)
            artifacts = state.get("artifacts") or {}
            summary["llm_used"] = bool(artifacts.get("llm_used"))
            summary["extraction"] = str(artifacts.get("extraction") or "deterministic")
        elif kind == "metrics":
            from lit_agent.eval.metrics import persist_run_metrics

            metrics = persist_run_metrics(ctx.settings, ctx.run_id)
            summary["metrics_persisted"] = True
            summary["claims_total"] = metrics.get("claims_total")
    return summary
