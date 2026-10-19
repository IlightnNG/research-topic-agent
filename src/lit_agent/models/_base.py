"""契约模型公共基类与共享标量。

设计要点（沿用 Phase 0，已被 19 个契约用例验证）：
- 所有契约模型 `extra="forbid"` + `frozen=True`：拼写错误在入口暴露，模型构造后不可变；
- 纯数据层：本包只允许 import 标准库与 pydantic，**不得** import 业务模块（保持契约可独立复用）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = [
    "ContractModel",
    "RunId",
    "Severity",
    "format_validation",
]

#: run 标识：Phase 0 用字符串（`p0-s5-001`），Phase 1 的 SQLite 主键用字符串 ULID；两者都允许。
RunId: TypeAlias = str


class Severity(StrEnum):
    """**日志/事件**的严重度（guide §1.4）。守卫判决另用 `GuardSeverity`，不要混用。"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ContractModel(BaseModel):
    """所有契约模型的基类：拒绝未知字段 + 不可变。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


def format_validation(exc: ValidationError) -> str:
    """把 pydantic 校验错误压成一行可读文本（用于日志与 CLI 提示）。"""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", ())) or "<root>"
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)


def dump_jsonable(value: Any) -> Any:  # pragma: no cover - 小工具
    """尽力把对象转成可 JSON 序列化的结构（供事件 payload 使用）。"""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    return value
