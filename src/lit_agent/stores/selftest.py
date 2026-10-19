"""存储层公共工具（Phase 1 先复用 `lit_agent.selftest` 的实现，Step 1.5 起在本包内扩展）。

保留这个模块的原因：`stores/` 是"派生物"层，它需要的路径/哨兵工具在 Phase 0 已被验证过，
先以 re-export 形式统一入口，避免调用方直接在 `lit_agent.selftest` 与 `stores` 之间做选择。
"""

from __future__ import annotations

from lit_agent.selftest import (
    assert_ascii_path,
    path_size_mb,
    read_store_meta,
    reset_store_path,
    sqlite_schema_version,
    store_is_empty,
)

__all__ = [
    "assert_ascii_path",
    "path_size_mb",
    "read_store_meta",
    "reset_store_path",
    "sqlite_schema_version",
    "store_is_empty",
]
