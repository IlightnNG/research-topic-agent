"""运行控制（S2）：abort 标记。单机单进程，进程内集合足够。"""

from __future__ import annotations

_ABORTED: set[str] = set()


def request_abort(run_id: str) -> None:
    _ABORTED.add(run_id)


def is_aborted(run_id: str) -> bool:
    return run_id in _ABORTED


def clear(run_id: str) -> None:
    _ABORTED.discard(run_id)
