"""主题与抓取范围仓储（`topics` / `topic_sources`）。"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_topic_sources, t_topics
from lit_agent.models.topic import Topic

__all__ = [
    "count",
    "get",
    "get_sources",
    "list_all",
    "set_status",
    "upsert",
    "upsert_sources",
]


def upsert(conn: Connection, topic: Topic, *, now: str | None = None) -> None:
    stamp = now or utcnow_iso()
    values = {
        "id": topic.id,
        "name": topic.name,
        "description": topic.description,
        "scope_statement": topic.scope_statement,
        "scope_keywords_json": json.dumps(topic.scope_keywords, ensure_ascii=False),
        "seed_queries_json": json.dumps(topic.seed_queries, ensure_ascii=False),
        "status": topic.status.value,
        "schedule_cron": topic.schedule_cron,
        "updated_at": stamp,
    }
    stmt = sqlite_insert(t_topics).values(created_at=stamp, **values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_topics.c.id],
        set_={key: getattr(stmt.excluded, key) for key in values if key != "id"},
    )
    conn.execute(stmt)


def upsert_sources(
    conn: Connection, topic_id: str, sources: Iterable[tuple[str, dict[str, Any]]]
) -> int:
    rows = [
        {
            "topic_id": topic_id,
            "source": source,
            "selector_json": json.dumps(selector, ensure_ascii=False, sort_keys=True),
        }
        for source, selector in sources
    ]
    if not rows:
        return 0
    stmt = sqlite_insert(t_topic_sources).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_topic_sources.c.topic_id, t_topic_sources.c.source],
        set_={"selector_json": stmt.excluded.selector_json},
    )
    conn.execute(stmt)
    return len(rows)


def get(conn: Connection, topic_id: str) -> Any:
    return conn.execute(select(t_topics).where(t_topics.c.id == topic_id)).first()


def list_all(conn: Connection) -> Sequence[Any]:
    return conn.execute(select(t_topics).order_by(t_topics.c.id)).all()


def get_sources(conn: Connection, topic_id: str) -> dict[str, dict[str, Any]]:
    stmt = select(t_topic_sources.c.source, t_topic_sources.c.selector_json).where(
        t_topic_sources.c.topic_id == topic_id
    )
    return {str(source): json.loads(selector) for source, selector in conn.execute(stmt).all()}


def set_status(conn: Connection, topic_id: str, status: str, *, now: str | None = None) -> None:
    conn.execute(
        t_topics.update()
        .where(t_topics.c.id == topic_id)
        .values(status=status, updated_at=now or utcnow_iso())
    )


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_topics)).scalar_one())
