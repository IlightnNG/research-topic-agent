"""run 编排（Phase 1 线性，Phase 2 换 LangGraph —— 见 §8.2 升级表）。

一次 run 的骨架：
`jobs.start`（拿锁）→ 逐阶段 `phase_change` 事件 → 每阶段后跑 GuardRail →
成功 `report_written` + succeeded；失败写**失败报告四要素** + error 事件 + failed。

阶段函数签名：`(RunContext) -> StageResult`，**不得自己吞异常**（失败要冒泡给 runner）。
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_UNEXPECTED, LitError
from lit_agent.graph.guards import guard_rail
from lit_agent.models._base import Severity
from lit_agent.models.event import EventType
from lit_agent.models.results import RunContext, StageResult
from lit_agent.models.run import RunState
from lit_agent.models.verdict import GuardAction
from lit_agent.runtime import jobs
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.events import SqliteEventLog

__all__ = ["StageFn", "default_stages", "run_topic"]

StageFn = Callable[[RunContext], StageResult]


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:10]}"


def _stage(name: str, produced: int = 1) -> StageFn:
    def run(ctx: RunContext) -> StageResult:
        return StageResult(
            stage=name, artifacts={"produced": produced}, metrics={f"{name}_ok": 1.0}
        )

    return run


def default_stages() -> dict[str, StageFn]:
    """Phase 1 的占位阶段链（真实抓取/解析在 1.12–1.16 接入）。"""
    return {
        "intake": _stage("intake", 1),
        "retrieve": _stage("retrieve", 1),
        "report": _stage("report", 1),
    }


def _load_cards(settings: Settings, limit: int = 50) -> list[Any]:
    """从 SQLite 取"主记录"论文 → 证据卡（Phase 1 不依赖 LLM）。"""
    from lit_agent.models.evidence import EvidenceCard

    active = make_engine(settings)
    try:
        with connect(active) as conn:
            rows = conn.execute(
                text(
                    "SELECT paper_id, title, COALESCE(abstract, ''), COALESCE(source, ''), year"
                    " FROM papers"
                    " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)"
                    " ORDER BY paper_id LIMIT :limit"
                ),
                {"limit": limit},
            ).all()
    finally:
        active.dispose()
    cards: list[Any] = []
    for paper_id, title, abstract, source, year in rows:
        snippet = (abstract or title or "").strip()[:400]
        if not snippet:
            continue
        cards.append(
            EvidenceCard(
                paper_id=str(paper_id),
                title=str(title or paper_id),
                snippet=snippet,
                source=str(source or "unknown"),
                year=int(year) if year is not None else None,
            )
        )
    return cards


def real_stages(settings: Settings) -> dict[str, StageFn]:
    """真实主干（P0-1）：intake → ingest → curate → report。

    - `ingest`：有 selector 才抓；没配置 selector（`E_SRC_NO_SELECTOR`）→ **降级继续**，
      因为"没配白名单"是配置状态而不是运行失败（报告会标 degraded）；
    - `curate`：去重 + 引用投影；
    - `report`：从库里取主记录建证据卡（不调 LLM）。
    """

    def intake(ctx: RunContext) -> StageResult:
        active = make_engine(settings)
        try:
            with connect(active) as conn:
                row = conn.execute(
                    text("SELECT id, status FROM topics WHERE id = :t"), {"t": ctx.topic_id}
                ).first()
        finally:
            active.dispose()
        if row is None:
            raise LitError(
                "E_CONFIG_INVALID",
                f"topic 不存在：{ctx.topic_id}",
                context={"topic_id": ctx.topic_id},
            )
        return StageResult(stage="intake", artifacts={"topic": ctx.topic_id, "status": str(row[1])})

    def ingest(ctx: RunContext) -> StageResult:
        from lit_agent.sources.sync import sync_topic

        try:
            result = sync_topic(settings, ctx.topic_id)
        except LitError as exc:
            if exc.code != "E_SRC_NO_SELECTOR":
                raise
            return StageResult(
                stage="ingest",
                artifacts={"skipped": "E_SRC_NO_SELECTOR"},
                metrics={"papers_new": 0.0, "papers_seen": 0.0},
            )
        return StageResult(
            stage="ingest",
            artifacts={
                "source": result.get("source"),
                "fetched": result.get("fetched", 0),
                "new": result.get("papers_new", 0),
            },
            metrics={
                "papers_new": float(result.get("papers_new", 0)),
                "papers_seen": float(result.get("papers_seen", result.get("fetched", 0))),
            },
        )

    def curate(ctx: RunContext) -> StageResult:
        from lit_agent.sources.dedup import project_citations, run_dedup

        dedup = run_dedup(settings)
        projection = project_citations(settings)
        return StageResult(
            stage="curate",
            artifacts={"unique": dedup["unique"], "edges": projection["edges_total"]},
            metrics={
                "merged_pairs": float(dedup["merged_pairs"]),
                "citation_edges": float(projection["edges_total"]),
            },
        )

    def report(ctx: RunContext) -> StageResult:
        cards = _load_cards(settings)
        return StageResult(
            stage="report",
            artifacts={"cards": len(cards)},
            metrics={"evidence_cards": float(len(cards))},
        )

    return {"intake": intake, "ingest": ingest, "curate": curate, "report": report}


def _set_stage(settings: Settings, run_id: str, stage: str, *, completed: bool) -> None:
    active = make_engine(settings)
    try:
        with connect(active, immediate=True) as conn:
            run_repo.set_stage(conn, run_id, stage, completed=completed)
    finally:
        active.dispose()


def run_topic(
    settings: Settings,
    topic_id: str,
    *,
    run_id: str | None = None,
    stages: Mapping[str, StageFn] | None = None,
    budget: RunBudget | None = None,
    no_progress_steps: int = 2,
) -> dict[str, Any]:
    """执行一次 run，返回摘要（含事件数与预算快照）。"""
    rid = run_id or new_run_id()
    chain = dict(stages or real_stages(settings))
    active = make_engine(settings)
    jobs.start(settings, topic_id, run_id=rid, engine=active)

    log = SqliteEventLog(active, rid)
    run_budget = budget or RunBudget(limit_usd=settings.routing.run_cost_budget_usd)
    rail = guard_rail(run_budget, no_progress_steps=no_progress_steps)
    produced = 0
    results: dict[str, Any] = {}

    try:
        log.emit(
            EventType.PHASE_CHANGE, stage="run", payload={"phase": "start", "topic_id": topic_id}
        )
        for name, stage_fn in chain.items():
            _set_stage(settings, rid, name, completed=False)
            log.emit(EventType.PHASE_CHANGE, stage=name, payload={"phase": "start"})

            result = stage_fn(RunContext(run_id=rid, topic_id=topic_id, stage=name))
            if not isinstance(result, StageResult):
                raise LitError(
                    E_UNEXPECTED,
                    f"阶段 {name} 返回了非 StageResult：{type(result).__name__}",
                    context={"stage": name},
                )
            # 守卫看**累计产出**（单调递增）：只有"连续 N 次没有增长"才是停滞。
            # 早期版本传"本阶段新增数"，占位阶段每步都是 1 → 被误判为停滞（已修）。
            produced += len(result.artifacts)
            verdict = rail.run({"produced": produced, "stage": name})
            if verdict is not None:
                log.emit(
                    EventType.GUARD_TRIGGER,
                    stage=name,
                    agent="guard",
                    severity=Severity.WARNING
                    if verdict.action is not GuardAction.ABORT
                    else Severity.ERROR,
                    payload=verdict.model_dump(mode="json"),
                )
                if verdict.action is GuardAction.ABORT:
                    raise LitError(
                        verdict.code, "守卫判定终止", context=verdict.model_dump(mode="json")
                    )

            log.emit(
                EventType.PHASE_CHANGE,
                stage=name,
                payload={
                    "phase": "end",
                    "metrics": result.metrics,
                    "artifacts": len(result.artifacts),
                },
            )
            _set_stage(settings, rid, name, completed=True)
            results[name] = result.model_dump(mode="json")

        # 报告落库：Phase 1 还没有证据链（检索/解析在 1.6/1.7 已有，但未接进 runner），
        # 因此先落一份**显式降级**报告（0 证据 → 1 条 unsupported claim），
        # 保证 `/api/runs/{id}/report` 可用、且不会伪造 grounding（DSH 对照 P0-2：产物与事件同事务）。
        report_id = _persist_report(settings, rid, topic_id, run_budget)
        jobs.finish(settings, rid, state=RunState.SUCCEEDED, engine=active)
        return {
            "run_id": rid,
            "state": RunState.SUCCEEDED.value,
            "stages": results,
            "report_id": report_id,
            "events": log.count(),
            "budget": run_budget.snapshot(),
        }
    except LitError as exc:
        report = jobs.failure_report(settings, rid, exc)
        log.emit(
            EventType.ERROR,
            stage="run",
            severity=Severity.ERROR,
            payload={**exc.to_event_payload(), "failure_report": report},
        )
        jobs.finish(settings, rid, state=RunState.FAILED, error_code=exc.code, engine=active)
        return {
            "run_id": rid,
            "state": RunState.FAILED.value,
            "error_code": exc.code,
            "failure_report": report,
            "events": log.count(),
            "budget": run_budget.snapshot(),
        }
    except BaseException:
        # 非预期异常（非 LitError）：也必须释放锁，否则 topic 会被锁到 180s 过期
        jobs.finish(settings, rid, state=RunState.ABORTED, error_code="E_UNEXPECTED", engine=active)
        raise
    finally:
        active.dispose()


#: 测试注入点：设为函数即可在**无 key / 无网络**下验证 LLM 摘要分支（生产恒为 None）。
_LLM_COMPLETER: Any | None = None


def _persist_claims(conn: Any, run_id: str, claims: list[Any]) -> int:
    """把报告 claims 写进 `claims` / `claim_citations`（幂等：同 run 同文本不重复）。"""
    from lit_agent.db.repo import claims as claim_repo

    if not claims:
        return 0
    claim_repo.insert_ignore_many(conn, run_id, claims)
    written = 0
    for claim in claims:
        digest = claim_repo.text_sha(claim.text)
        claim_id = f"{run_id}:{digest[:12]}"
        citations = [
            (citation.paper_id, None, citation.snippet, 1.0) for citation in (claim.citations or [])
        ]
        if citations:
            written += claim_repo.insert_citations_many(conn, claim_id, citations)
    return written


def _llm_summary(settings: Settings, budget: Any, cards: list[Any], *, run_id: str) -> str | None:
    """用网关生成 3 句摘要；无 key / 预算不足 / 调用失败 → 返回 None（显式降级）。"""
    from lit_agent.gateway.llm import LLMGateway

    if settings.providers.cloud.api_key is None and _LLM_COMPLETER is None:
        return None
    material = "\n".join(f"- {card.title}: {card.snippet[:200]}" for card in cards[:20])
    gateway = LLMGateway(settings, completer=_LLM_COMPLETER, budget=budget)
    try:
        call = gateway.chat(
            [
                {
                    "role": "system",
                    "content": "Summarize the literature evidence in 3 concise sentences. No citations needed.",
                },
                {"role": "user", "content": material},
            ],
            max_tokens=400,
            run_id=run_id,
            agent="reporter",
        )
        return call.content.strip() or None
    except LitError:
        return None
    finally:
        gateway.close()


def _persist_report(
    settings: Settings, run_id: str, topic_id: str, budget: Any | None = None
) -> str | None:
    """落报告 + 同事务写 `report_written` 事件（P1-①：产品与事件同事务）。

    证据来自库里已有论文（`_load_cards`）；没有论文时报告显式 `degraded`，
    claims 为 1 条 unsupported（**不伪造 grounding**）。
    """
    from lit_agent.agents.reporter import build_report
    from lit_agent.db.repo import reports as report_repo

    cards = _load_cards(settings)
    draft = build_report(
        cards, topic_id=topic_id, run_id=run_id, title=f"Weekly report: {topic_id}"
    )
    draft = draft.model_copy(update={"degraded": not cards})

    # D8：有 key 时才走 LLM 摘要；摘要失败**不影响主链路**（报告回落到确定性渲染）。
    # 网关与 run 共用同一个 RunBudget → 摘要成本会累加到本次 run 的预算里。
    if cards and budget is not None:
        summary = _llm_summary(settings, budget, cards, run_id=run_id)
        if summary:
            body = f"## Summary (LLM)\n\n{summary}\n\n{draft.content_md}"
            draft = draft.model_copy(
                update={
                    "content_md": body,
                    "content_sha": hashlib.sha256(body.encode("utf-8")).hexdigest()[:12],
                }
            )
    active = make_engine(settings)
    try:
        with connect(active, immediate=True) as conn:
            report_repo.insert_ignore(conn, draft)
            # F5：claims 必须落库（此前只写 reports.claims_json → 指标 claims 恒为 0）
            _persist_claims(conn, run_id, draft.claims)
            SqliteEventLog(active, run_id).emit(
                EventType.REPORT_WRITTEN,
                stage="report",
                payload={
                    "run_id": run_id,
                    "report_id": draft.report_id,
                    "degraded": draft.degraded,
                    "claims": draft.n_claims,
                    "cards": len(cards),
                },
                conn=conn,
            )
    finally:
        active.dispose()
    return draft.report_id


def run_counts(settings: Settings) -> dict[str, int]:
    active = make_engine(settings)
    try:
        with connect(active) as conn:
            return {
                "runs": run_repo.count(conn),
                "events": int(conn.execute(text("SELECT COUNT(*) FROM run_events")).scalar_one()),
            }
    finally:
        active.dispose()
