"""故障注入（S11 落地，S6 先给三种可测的最小故障）。

用法：

    with inject("empty_retrieval"):
        ...  # 检索返回空
    with inject("bad_artifact"):
        ...  # 分析产出无引用 claim
    with inject("timeout"):
        ...  # 进入即抛 E_SRC_TIMEOUT

生产默认不激活；`is_active()` 供被测代码查询。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from lit_agent.errors import E_SRC_TIMEOUT, LitError

__all__ = ["KINDS", "inject", "is_active"]

KINDS = ("empty_retrieval", "bad_artifact", "timeout")
_ACTIVE: set[str] = set()


def is_active(kind: str) -> bool:
    return kind in _ACTIVE


@contextmanager
def inject(kind: str = "empty_retrieval") -> Iterator[None]:
    if kind not in KINDS:
        raise ValueError(f"未知故障类型：{kind}")
    _ACTIVE.add(kind)
    try:
        if kind == "timeout":
            raise LitError(E_SRC_TIMEOUT, "注入故障：数据源超时", context={"fault": kind})
        yield
    finally:
        _ACTIVE.discard(kind)
