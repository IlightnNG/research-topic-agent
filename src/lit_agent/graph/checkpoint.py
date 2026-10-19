"""SQLite checkpoint 接线（guide §6 / Phase 0 结论）。

Phase 0 的坑（已固化为本模块行为）
- 续跑必须 `invoke(None)`：带输入会从 START 重放，导致重复抓取；
- 崩溃的节点会**重新执行**，因此节点必须自身幂等（P2-GRAPH-02 依赖此约定）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

__all__ = ["open_checkpointer", "resume", "thread_config"]


def thread_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def open_checkpointer(db_path: str | Path) -> tuple[Any, sqlite3.Connection]:
    """返回 (`SqliteSaver`, 连接)；调用方负责 `connection.close()`。"""
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(connection)
    setup = getattr(saver, "setup", None)
    if callable(setup):
        setup()
    return saver, connection


def resume(graph: Any, run_id: str) -> dict[str, Any]:
    """从 checkpoint 续跑：**只允许 `None`**，禁止带输入重放。"""
    return graph.invoke(None, thread_config(run_id))
