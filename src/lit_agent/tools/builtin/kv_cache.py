"""内置工具：进程内 KV 缓存（D-MIN）。

Phase 1 用内存字典（进程内有效、可复现、零依赖）；跨 run 的持久缓存已在
`llm_cache` / `embeddings` 表实现，本工具只服务"单次 run 内的中间结果暂存"。
"""

from __future__ import annotations

import time
from typing import Any

from lit_agent.tools.registry import Tool

__all__ = ["build_tool", "clear", "get", "put"]

_STORE: dict[str, tuple[Any, float | None]] = {}


def put(key: str, value: Any, *, ttl_s: float | None = None) -> None:
    expires = (time.monotonic() + ttl_s) if ttl_s else None
    _STORE[key] = (value, expires)


def get(key: str) -> Any:
    entry = _STORE.get(key)
    if entry is None:
        return None
    value, expires = entry
    if expires is not None and time.monotonic() >= expires:
        _STORE.pop(key, None)
        return None
    return value


def clear() -> None:
    _STORE.clear()


def build_tool() -> Tool:
    def run(*, action: str, key: str = "", value: Any = None, ttl_s: float | None = None) -> Any:
        if action == "put":
            put(key, value, ttl_s=ttl_s)
            return True
        if action == "get":
            return get(key)
        if action == "clear":
            clear()
            return True
        raise ValueError(f"未知 action：{action}")

    return Tool(
        name="kv_cache",
        run=run,
        description="In-process key-value cache for intermediate run artifacts",
        parameters={
            "action": "put|get|clear",
            "key": "string",
            "value": "any?",
            "ttl_s": "number?",
        },
    )
