"""SQLite 真相源层（guide §2.1 + ADR-0005）。

- `db.base`：`metadata` 与时间工具
- `db.tables`：24 张表的 DDL（契约唯一来源）
- `db.session`：引擎/事务/迁移/schema 守卫
- `db.repo`：幂等仓储（唯一写入口）
"""

from __future__ import annotations

from lit_agent.db.base import metadata

__all__ = ["metadata"]
