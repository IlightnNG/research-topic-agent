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
    finally:
        engine.dispose()

    return {
        "scope": "topic" if topic_id else "global",
        "scope_id": topic_id or "*",
        "papers": int(papers),
        "paper_merges": int(merges),
        "claims": int(claims),
        "cost_usd": round(cost, 6),
        "cost_estimated_calls": int(estimated),
        "grounding_rate": _ratio(supported, claims),
        "hallucination_rate": _ratio(unsupported, claims),
        "citation_coverage": _ratio(cited, claims),
        "dedup_rate": _ratio(merges, papers),
    }


def compute_run_metrics(settings: Settings, run_id: str) -> dict[str, Any]:
    """单 run 指标（`scope='run'`）。"""
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic = conn.execute(
                text("SELECT topic_id FROM runs WHERE id = :rid"), {"rid": run_id}
            ).scalar_one_or_none()
    finally:
        engine.dispose()
    metrics = compute_topic_metrics(settings, topic_id=str(topic) if topic else None)
    metrics["scope"] = "run"
    metrics["scope_id"] = run_id
    return metrics


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
    finally:
        engine.dispose()
    return metrics
