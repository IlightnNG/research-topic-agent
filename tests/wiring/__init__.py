"""公共夹具：S1 接线测试用（临时 store + 一个 topic + 一篇有摘要的论文）。"""

from __future__ import annotations

from pathlib import Path

from lit_agent.config import (
    GateSettings,
    LoggingSettings,
    PipelineSettings,
    Settings,
    StorageSettings,
)
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic


def prepare(
    tmp_path: Path,
    *,
    papers: int = 1,
    specs: list[tuple[str, str]] | None = None,
    scope: str = "agents",
) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
        # 小夹具只有 1 篇论文：显式把证据阈值设为 1，避免把"阈值测试"混进其他用例
        pipeline=PipelineSettings(gates=GateSettings(evidence_min_cards=1)),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement=scope))
            items = specs or [
                (f"Paper {index}", "tool use improves task success") for index in range(papers)
            ]
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id=f"P{index}",
                        title=title,
                        abstract=abstract,
                        source="arxiv",
                    )
                    for index, (title, abstract) in enumerate(items)
                ],
            )
    finally:
        engine.dispose()
    return settings


def fetch_events(settings: Settings, run_id: str) -> list[dict]:
    import json

    from sqlalchemy import text

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT type, stage, payload_json FROM run_events"
                    " WHERE run_id = :rid ORDER BY seq"
                ),
                {"rid": run_id},
            ).all()
    finally:
        engine.dispose()
    return [
        {"type": row[0], "stage": row[1], "payload": json.loads(row[2] or "{}")}
        for row in rows
    ]
