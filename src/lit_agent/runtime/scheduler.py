"""APScheduler 装配（Phase 1：**默认 disabled，不注册任何 job**）。

启用时也只注册一个"周更"job；`run-once` 走同一函数（便于手工验证）。
真实周期化（stagger、失败补偿、两周期验收）在 P4。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine
from lit_agent.runtime.runner import run_topic

__all__ = ["build_scheduler", "cron_kwargs", "list_jobs", "run_once", "weekly_job"]


def cron_kwargs(expression: str) -> dict[str, str]:
    """把 5 段 cron 解析成 APScheduler 的 kwargs。"""
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(f"cron 必须是 5 段：{expression!r}")
    minute, hour, day, month, day_of_week = parts
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def _active_topics(settings: Settings) -> list[str]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text("SELECT id FROM topics WHERE status = 'active' ORDER BY id")
            ).all()
    finally:
        engine.dispose()
    return [str(row[0]) for row in rows]


def weekly_job(settings: Settings, topic_id: str | None = None) -> dict[str, Any]:
    """跑一轮周更：默认遍历所有 active topic。"""
    topic_ids = [topic_id] if topic_id else _active_topics(settings)
    results: dict[str, Any] = {}
    for item in topic_ids:
        result = run_topic(settings, item)
        # P1：runner 还没有 trigger 参数，这里回填以便区分手动/定时（P2 改为参数下传）
        engine = make_engine(settings)
        try:
            with connect(engine, immediate=True) as conn:
                conn.execute(
                    text("UPDATE runs SET trigger = 'schedule' WHERE id = :rid"),
                    {"rid": result["run_id"]},
                )
        finally:
            engine.dispose()
        results[item] = {"run_id": result["run_id"], "state": result["state"]}
    return {"topics": topic_ids, "results": results}


def build_scheduler(settings: Settings) -> Any:
    """构造调度器；`enabled=False` 时**不注册 job**。"""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone=settings.scheduler.timezone)
    if not settings.scheduler.enabled:
        return scheduler
    scheduler.add_job(
        func=lambda: weekly_job(settings),
        trigger="cron",
        id="weekly",
        name="weekly-report",
        replace_existing=True,
        **cron_kwargs(settings.scheduler.default_cron),
    )
    return scheduler


def list_jobs(scheduler: Any) -> list[dict[str, Any]]:
    return [
        {"id": job.id, "name": job.name, "next_run": str(getattr(job, "next_run_time", None))}
        for job in scheduler.get_jobs()
    ]


def run_once(settings: Settings, topic_id: str) -> dict[str, Any]:
    """手工跑一次（等价于到点触发），用于验证调度链路。"""
    return weekly_job(settings, topic_id)
