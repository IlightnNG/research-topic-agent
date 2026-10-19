"""LLM 调用计量与内容寻址缓存仓储。

- `llm_calls`：**append-only**——真实发生的调用就是事实，重试产生多行是正确的；
- `llm_cache`：`request_sha` 主键；命中只 `hit_count+1`，绝不覆盖缓存响应（可复现性来源，F8）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_llm_cache, t_llm_calls

__all__ = [
    "cache_get",
    "cache_hit",
    "cache_put",
    "record",
    "summary_by_run",
    "total_cost",
]


def record(
    conn: Connection,
    *,
    ts: str | None = None,
    run_id: str | None,
    agent: str | None,
    provider: str,
    model: str,
    route_reason: str | None,
    request_sha: str,
    cache_hit: bool = False,
    req_tokens: int | None = None,
    resp_tokens: int | None = None,
    cost: float | None = None,
    cost_estimated: bool = False,
    latency_ms: int | None = None,
    degraded: bool = False,
    ok: bool = True,
    error_code: str | None = None,
) -> None:
    conn.execute(
        t_llm_calls.insert().values(
            ts=ts or utcnow_iso(),
            run_id=run_id,
            agent=agent,
            provider=provider,
            model=model,
            route_reason=route_reason,
            request_sha=request_sha,
            cache_hit=int(cache_hit),
            req_tokens=req_tokens,
            resp_tokens=resp_tokens,
            cost=cost,
            cost_estimated=int(cost_estimated),
            latency_ms=latency_ms,
            degraded=int(degraded),
            ok=int(ok),
            error_code=error_code,
        )
    )


def summary_by_run(conn: Connection, run_id: str) -> dict[str, Any]:
    """单 run 的调用统计（成本、token、缓存命中、失败数）。"""
    row = conn.execute(
        text(
            """
            SELECT COUNT(*)                                   AS calls,
                   COALESCE(SUM(cost), 0.0)                   AS cost,
                   COALESCE(SUM(req_tokens), 0)               AS req_tokens,
                   COALESCE(SUM(resp_tokens), 0)              AS resp_tokens,
                   COALESCE(SUM(cache_hit), 0)                AS cache_hits,
                   COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) AS failures,
                   COALESCE(SUM(cost_estimated), 0)           AS estimated_calls
            FROM llm_calls WHERE run_id = :run_id
            """
        ),
        {"run_id": run_id},
    ).first()
    if row is None:
        return {}
    mapping = row._mapping
    return {
        "calls": int(mapping["calls"]),
        "cost_usd": round(float(mapping["cost"]), 6),
        "req_tokens": int(mapping["req_tokens"]),
        "resp_tokens": int(mapping["resp_tokens"]),
        "cache_hits": int(mapping["cache_hits"]),
        "failures": int(mapping["failures"]),
        "estimated_calls": int(mapping["estimated_calls"]),
    }


def total_cost(conn: Connection) -> float:
    value = conn.execute(select(func.coalesce(func.sum(t_llm_calls.c.cost), 0.0))).scalar_one()
    return round(float(value), 6)


def cache_get(conn: Connection, request_sha: str) -> Any:
    stmt = select(t_llm_cache).where(t_llm_cache.c.request_sha == request_sha)
    return conn.execute(stmt).first()


def cache_put(
    conn: Connection,
    request_sha: str,
    *,
    model: str,
    response_json: str,
    usage_json: str | None = None,
    now: str | None = None,
) -> int:
    """写缓存：已存在则**不覆盖**（返回 0）。"""
    stmt = (
        sqlite_insert(t_llm_cache)
        .values(
            request_sha=request_sha,
            model=model,
            response_json=response_json,
            usage_json=usage_json,
            created_at=now or utcnow_iso(),
        )
        .on_conflict_do_nothing(index_elements=[t_llm_cache.c.request_sha])
    )
    result = conn.execute(stmt)
    return int(result.rowcount or 0)


def cache_hit(conn: Connection, request_sha: str) -> None:
    conn.execute(
        text("UPDATE llm_cache SET hit_count = hit_count + 1 WHERE request_sha = :sha"),
        {"sha": request_sha},
    )
