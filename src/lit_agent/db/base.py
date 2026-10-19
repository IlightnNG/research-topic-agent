"""SQLAlchemy 元数据与共享工具。

约定
- **表结构唯一来源 = `db/tables.py`**；Alembic 迁移直接从同一份 `metadata` 生成，
  保证"代码里的表"与"迁移建出的表"不可能漂移（Phase 0 的静默错误 #1 从此不会复发）；
- 所有时间列是 `TEXT` ISO-8601 UTC 字符串（ADR-0005 §3），便于 SQLite 上做字典序比较与跨库导出。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import MetaData

__all__ = ["metadata", "parse_iso", "utcnow_iso"]

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow_iso() -> str:
    """当前 UTC 时间（秒级精度，Z 后缀）。"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    """把库里的 ISO 字符串解析回带时区的 datetime（解析失败返回 None）。"""
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
