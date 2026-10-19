"""Topic CRUD 与触发运行（Phase 1 同步执行；异步化留 P2）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.api.schemas import RunRequest, TopicCreate
from lit_agent.config import Settings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect
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
                "E_CONFIG_INVALID", f"topic 不存在：{topic_id}", context={"topic_id": topic_id}
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
    from lit_agent.runtime.runner import run_topic

    body = payload or RunRequest()
    budget = RunBudget(limit_usd=body.max_usd or settings.routing.run_cost_budget_usd)
    result = run_topic(settings, topic_id, run_id=body.run_id, budget=budget)
    return {"run_id": result["run_id"], "state": result["state"], "events": result["events"]}


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
