"""运行控制（S2）：abort 标记。单机单进程，进程内集合足够。"""

from __future__ import annotations

_ABORTED: set[str] = set()


def request_abort(run_id: str) -> None:
    _ABORTED.add(run_id)


def is_aborted(run_id: str) -> bool:
    return run_id in _ABORTED


def clear(run_id: str) -> None:
    _ABORTED.discard(run_id)


# ---------------- pause / inject（S9） ----------------
_PAUSED: set[str] = set()
_INJECT: dict[str, list[str]] = {}


def request_pause(run_id: str) -> None:
    _PAUSED.add(run_id)


def is_paused(run_id: str) -> bool:
    return run_id in _PAUSED


def clear_pause(run_id: str) -> None:
    _PAUSED.discard(run_id)


def inject_prompt(run_id: str, text: str) -> None:
    _INJECT.setdefault(run_id, []).append(text)


def consume_inject(run_id: str) -> list[str]:
    """取走并清空注入的提示词（续跑时合并进 focus_hint）。"""
    return _INJECT.pop(run_id, [])


def pending_inject(run_id: str) -> list[str]:
    return list(_INJECT.get(run_id, []))
