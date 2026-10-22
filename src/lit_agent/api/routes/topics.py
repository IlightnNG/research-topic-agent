"""Topic CRUD 与触发运行（Phase 1 同步执行；异步化留 P2）。"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.api.schemas import RunRequest, TopicCreate, TopicUpdate
from lit_agent.config import Settings
from lit_agent.db.base import utcnow_iso
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_CONFIG_INVALID, E_NOT_FOUND, LitError
from lit_agent.models.topic import Topic

router = APIRouter()


def _out(row: Any) -> dict[str, Any]:
    data = dict(row._mapping)
    data.pop("scope_keywords_json", None)
    data.pop("seed_queries_json", None)
    data.pop("config_json", None)
    return data


@router.get("")
def list_topics(
    settings: Settings = Depends(get_settings), engine: Any = Depends(get_engine)
) -> list[dict[str, Any]]:
    with connect(engine) as conn:
        return [_out(row) for row in topic_repo.list_all(conn)]


@router.post("", status_code=201)
def create_topic(
    payload: TopicCreate,
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    topic = Topic(
        id=payload.id,
        name=payload.name,
        description=payload.description,
        scope_statement=payload.scope_statement,
        scope_keywords=payload.scope_keywords,
        seed_queries=payload.seed_queries,
    )
    sources = [
        (str(item.get("source") or ""), item.get("selector") or {})
        for item in payload.sources
        if item.get("source")
    ]
    with connect(engine, immediate=True) as conn:
        topic_repo.upsert(conn, topic)
        if sources:
            topic_repo.upsert_sources(conn, topic.id, sources)
    return {"id": topic.id, "name": topic.name, "sources": [s for s, _ in sources]}


@router.get("/{topic_id}")
def get_topic(topic_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    from lit_agent.errors import LitError

    with connect(engine) as conn:
        row = topic_repo.get(conn, topic_id)
        if row is None:
            raise LitError(
                "E_NOT_FOUND", f"topic 不存在：{topic_id}", context={"topic_id": topic_id}
            )
        data = _out(row)
        data["sources"] = topic_repo.get_sources(conn, topic_id)
        return data


@router.post("/{topic_id}/run")
def trigger_run(
    topic_id: str,
    payload: RunRequest | None = None,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    from lit_agent.runtime.budget import RunBudget
    from lit_agent.runtime.graph_runner import run_graph

    body = payload or RunRequest()
    budget = RunBudget(limit_usd=body.max_usd or settings.routing.run_cost_budget_usd)

    if body.wait:
        result = run_graph(
            settings,
            topic_id,
            run_id=body.run_id,
            budget=budget,
            focus_hint=body.focus_hint,
        )
        return {
            "run_id": result["run_id"],
            "state": result["state"],
            "events": result.get("events", 0),
        }

    # S2：异步执行。**先在请求线程里建 run 行 + 拿锁**（批次 1 / B）：
    # 这样 202 返回时 run 一定可查；锁冲突直接 → 409，不会出现"幽灵 run"。
    from lit_agent.runtime.runner import prepare_run

    run_id = body.run_id or f"run-{uuid.uuid4().hex[:10]}"
    prepare_run(settings, topic_id, run_id, body.focus_hint)
    threading.Thread(
        target=run_graph,
        kwargs={
            "settings": settings,
            "topic_id": topic_id,
            "run_id": run_id,
            "budget": budget,
            "focus_hint": body.focus_hint,
            "prestarted": True,
            "resume": False,
        },
        daemon=True,
        name=f"run-{run_id}",
    ).start()
    return JSONResponse(status_code=202, content={"run_id": run_id, "state": "queued"})


@router.get("/{topic_id}/counts")
def topic_counts(topic_id: str, engine: Any = Depends(get_engine)) -> dict[str, int]:
    with connect(engine) as conn:
        runs = conn.execute(
            text("SELECT COUNT(*) FROM runs WHERE topic_id = :t"), {"t": topic_id}
        ).scalar_one()
        reports = conn.execute(
            text("SELECT COUNT(*) FROM reports WHERE topic_id = :t"), {"t": topic_id}
        ).scalar_one()
    return {"runs": int(runs), "reports": int(reports)}


@router.get("/{topic_id}/runs")
def list_runs(
    topic_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    """S1：run 列表（左栏数据源）。含 period / focus_hint / report_id / cost。"""
    with connect(engine) as conn:
        rows = conn.execute(
            text(
                "SELECT r.id, r.period, r.state, r.stage, r.trigger, r.focus_hint,"
                " r.error_code, r.started_at, r.finished_at,"
                " (SELECT report_id FROM reports WHERE run_id = r.id) AS report_id,"
                " (SELECT COALESCE(SUM(cost), 0.0) FROM llm_calls WHERE run_id = r.id) AS cost_usd"
                " FROM runs r WHERE r.topic_id = :t"
                " ORDER BY COALESCE(r.period, '') DESC, r.created_at DESC"
                " LIMIT :limit OFFSET :offset"
            ),
            {"t": topic_id, "limit": limit, "offset": offset},
        ).all()
    items = [dict(row._mapping) for row in rows]
    return {"topic_id": topic_id, "items": items, "count": len(items)}


@router.patch("/{topic_id}")
def patch_topic(
    topic_id: str,
    payload: TopicUpdate,
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    """S1：重命名 / 改 scope / 归档（status）。只允许这三个白名单字段。"""
    allowed = {"name", "description", "scope_statement", "status"}
    fields = dict(payload.model_dump(exclude_none=True))
    # 批次 3 / K：status 只能是枚举值（否则前端"归档/恢复"会写入垃圾状态）
    if "status" in fields and fields["status"] not in {"active", "archived"}:
        raise LitError(
            E_CONFIG_INVALID,
            f"status 只能是 active/archived：{fields['status']!r}",
            context={"status": fields["status"]},
        )
    unknown = set(fields) - allowed
    if unknown:
        raise LitError(
            E_CONFIG_INVALID,
            f"不支持修改的字段：{sorted(unknown)}",
            context={"allowed": sorted(allowed)},
        )
    if not fields:
        raise LitError(E_CONFIG_INVALID, "没有要修改的字段")
    fields["updated_at"] = utcnow_iso()
    sets = ", ".join(f"{key} = :{key}" for key in fields)
    with connect(engine, immediate=True) as conn:
        conn.execute(
            text(f"UPDATE topics SET {sets} WHERE id = :topic_id"),
            {**fields, "topic_id": topic_id},
        )
        row = topic_repo.get(conn, topic_id)
        if row is None:
            raise LitError(E_NOT_FOUND, f"topic 不存在：{topic_id}", context={"topic_id": topic_id})
        data = dict(row._mapping)
    for key in ("scope_keywords_json", "seed_queries_json", "config_json"):
        data.pop(key, None)
    return data
