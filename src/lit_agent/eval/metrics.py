"""指标聚合：**只读事件与库**，不调用业务写路径（guide §12 / ADR-0002）。

Phase 1 的 5 项（口径固定、可复算）：
- `grounding_rate = supported / claims`
- `hallucination_rate = unsupported / claims`
- `citation_coverage = 至少 1 条引用的 claims / claims`
- `dedup_rate = paper_merges / 主记录数`
- `cost_usd = SUM(llm_calls.cost)`（`cost_estimated` 单列计数）

**分母为 0 时返回 `None`**：`"算不出来"` 与 `"就是 0"` 必须可区分（Phase 0 假指标的根源）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.base import utcnow_iso
from lit_agent.db.session import connect, make_engine

__all__ = ["compute_run_metrics", "compute_topic_metrics", "persist_run_metrics"]


def _value(conn: Any, sql: str, params: dict[str, Any]) -> float:
    return float(conn.execute(text(sql), params).scalar_one_or_none() or 0.0)


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator <= 0 else round(numerator / denominator, 4)


def _scope_clause(topic_id: str | None) -> tuple[str, str, dict[str, Any]]:
    """返回 (WHERE 子句, 追加条件连接词, 参数)。`""` 表示不过滤。"""
    if topic_id:
        return "WHERE r.topic_id = :topic", "AND", {"topic": topic_id}
    return "", "WHERE", {}


_CLAIMS = "FROM claims c JOIN runs r ON r.id = c.run_id"
_LLM = "FROM llm_calls l JOIN runs r ON r.id = l.run_id"


def compute_topic_metrics(settings: Settings, *, topic_id: str | None = None) -> dict[str, Any]:
    """topic 级（或全局）指标。"""
    where, conj, params = _scope_clause(topic_id)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            papers = _value(
                conn,
                "SELECT COUNT(*) FROM papers"
                " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)",
                {},
            )
            merges = _value(conn, "SELECT COUNT(*) FROM paper_merges", {})
            claims = _value(conn, f"SELECT COUNT(*) {_CLAIMS} {where}", params)
            supported = _value(
                conn,
                f"SELECT COUNT(*) {_CLAIMS} {where} {conj} c.support = 'supported'",
                params,
            )
            unsupported = _value(
                conn,
                f"SELECT COUNT(*) {_CLAIMS} {where} {conj} c.support = 'unsupported'",
                params,
            )
            cited = _value(
                conn,
                "SELECT COUNT(DISTINCT c.claim_id)"
                " FROM claims c"
                " JOIN runs r ON r.id = c.run_id"
                " JOIN claim_citations cc ON cc.claim_id = c.claim_id"
                f" {where}",
                params,
            )
            cost = _value(conn, f"SELECT COALESCE(SUM(l.cost), 0.0) {_LLM} {where}", params)
            estimated = _value(
                conn,
                f"SELECT COUNT(*) {_LLM} {where} {conj} l.cost_estimated = 1",
                params,
            )
            # S13：成本归因到 agent 维度
            by_agent = conn.execute(
                text(
                    "SELECT l.agent, COUNT(*), COALESCE(SUM(l.cost), 0.0)"
                    f" {_LLM} {where} {conj} l.agent IS NOT NULL GROUP BY l.agent"
                ),
                params,
            ).all()
    finally:
        engine.dispose()

    return {
        "scope": "topic" if topic_id else "global",
        "scope_id": topic_id or "*",
        "papers": int(papers),
        "paper_merges": int(merges),
        "claims": int(claims),
        # F5：报告口径对齐用的显式分子/分母（报告 `n_claims` 必须等于 `claims_total`）
        "claims_total": int(claims),
        "claims_supported": int(supported),
        "cost_usd": round(cost, 6),
        "cost_estimated_calls": int(estimated),
        "cost_by_agent": {str(agent): round(float(item_cost), 6) for agent, _n, item_cost in by_agent},
        "calls_by_agent": {str(agent): int(count) for agent, count, _item_cost in by_agent},
        "agents_used": len(by_agent),
        "grounding_rate": _ratio(supported, claims),
        "hallucination_rate": _ratio(unsupported, claims),
        "citation_coverage": _ratio(cited, claims),
        "dedup_rate": _ratio(merges, papers),
    }


def compute_run_metrics(settings: Settings, run_id: str) -> dict[str, Any]:
    """单 run 指标（`scope='run'`）：**只统计本 run**，不混入历史 run。"""
    from lit_agent.eval.grounding import check_claim
    from lit_agent.models.claim import Claim
    from lit_agent.models.evidence import Citation

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic = conn.execute(
                text("SELECT topic_id FROM runs WHERE id = :rid"), {"rid": run_id}
            ).scalar_one_or_none()

            claim_rows = conn.execute(
                text(
                    "SELECT c.claim_id, c.text, c.support"
                    " FROM claims c WHERE c.run_id = :rid ORDER BY c.created_at"
                ),
                {"rid": run_id},
            ).all()
            citation_rows = conn.execute(
                text(
                    "SELECT cc.claim_id, cc.paper_id, COALESCE(cc.snippet,'')"
                    " FROM claim_citations cc JOIN claims c ON c.claim_id = cc.claim_id"
                    " WHERE c.run_id = :rid"
                ),
                {"rid": run_id},
            ).all()

            cost_row = conn.execute(
                text(
                    "SELECT COALESCE(SUM(cost), 0.0),"
                    " COALESCE(SUM(CASE WHEN cost_estimated = 1 THEN 1 ELSE 0 END), 0),"
                    " COUNT(*)"
                    " FROM llm_calls WHERE run_id = :rid"
                ),
                {"rid": run_id},
            ).one()
            by_agent = conn.execute(
                text(
                    "SELECT agent, COUNT(*), COALESCE(SUM(cost), 0.0)"
                    " FROM llm_calls WHERE run_id = :rid AND agent IS NOT NULL"
                    " GROUP BY agent"
                ),
                {"rid": run_id},
            ).all()
            papers = _value(
                conn,
                "SELECT COUNT(*) FROM papers"
                " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)",
                {},
            )
            merges = _value(conn, "SELECT COUNT(*) FROM paper_merges", {})
    finally:
        engine.dispose()

    citations_by_claim: dict[str, list[Citation]] = {}
    for claim_id, paper_id, snippet in citation_rows:
        citations_by_claim.setdefault(str(claim_id), []).append(
            Citation(paper_id=str(paper_id), snippet=str(snippet) or None)
        )

    claims = int(len(claim_rows))
    supported_db = sum(1 for _claim_id, _text_, support in claim_rows if support == "supported")
    cited = len(citations_by_claim)

    # grounding 由**判定器**给出（不是拿 support 自证）
    grounded = 0
    for claim_id, claim_text, _support in claim_rows:
        claim = Claim(
            text=str(claim_text),
            citations=citations_by_claim.get(str(claim_id), []),
        )
        if check_claim(claim).supported:
            grounded += 1

    cost, estimated, _calls = (float(cost_row[0]), int(cost_row[1]), int(cost_row[2]))
    return {
        "scope": "run",
        "scope_id": run_id,
        "topic_id": str(topic) if topic else None,
        "papers": int(papers),
        "paper_merges": int(merges),
        "claims": claims,
        "claims_total": claims,
        "claims_supported": int(supported_db),  # 兼容旧口径（DB support 字段）
        "claims_supported_db": int(supported_db),
        "claims_grounded": grounded,
        "cost_usd": round(cost, 6),
        "cost_estimated_calls": estimated,
        "cost_by_agent": {
            str(agent): round(float(item_cost), 6) for agent, _n, item_cost in by_agent
        },
        "calls_by_agent": {str(agent): int(count) for agent, count, _c in by_agent},
        "agents_used": len(by_agent),
        "grounding_rate": _ratio(grounded, claims),
        "supported_rate_db": _ratio(supported_db, claims),
        "hallucination_rate": _ratio(claims - grounded, claims),
        "citation_coverage": _ratio(cited, claims),
        "dedup_rate": _ratio(merges, papers),
    }


def persist_run_metrics(settings: Settings, run_id: str) -> dict[str, Any]:
    """写入 `metrics`（可复算：同 `(scope, scope_id, metric)` 覆盖，行数不增长）。"""
    metrics = compute_run_metrics(settings, run_id)
    stage = utcnow_iso()
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            for key, value in metrics.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                conn.execute(
                    text(
                        "INSERT INTO metrics(scope, scope_id, metric, value, ts)"
                        " VALUES ('run', :sid, :metric, :value, :ts)"
                        " ON CONFLICT(scope, scope_id, metric)"
                        " DO UPDATE SET value = excluded.value, ts = excluded.ts"
                    ),
                    {"sid": run_id, "metric": key, "value": float(value), "ts": stage},
                )
            # S13：成本按 agent 落库（scope='agent'，scope_id='<run_id>:<agent>'）
            for agent, cost in (metrics.get("cost_by_agent") or {}).items():
                conn.execute(
                    text(
                        "INSERT INTO metrics(scope, scope_id, metric, value, ts)"
                        " VALUES ('agent', :sid, 'cost_usd', :value, :ts)"
                        " ON CONFLICT(scope, scope_id, metric)"
                        " DO UPDATE SET value = excluded.value, ts = excluded.ts"
                    ),
                    {"sid": f"{run_id}:{agent}", "value": float(cost), "ts": stage},
                )
    finally:
        engine.dispose()
    return metrics
