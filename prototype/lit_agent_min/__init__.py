"""lit_agent_min —— Phase 0 最小可复用内核。

公开入口：
- `load_settings()` / `ConfigError`：配置加载与可预期错误
- `selfcheck()`：导入自检（版本 → 配置 → 目录 → 密钥），返回进程退出码
"""

from __future__ import annotations

import sys
from pathlib import Path

from .config import (
    ConfigError,
    Settings,
    default_config_path,
    ensure_dirs,
    ensure_env,
    load_settings,
    missing_env,
    project_root,
)

__version__ = "0.1.0"

__all__ = [
    "ConfigError",
    "Settings",
    "__version__",
    "default_config_path",
    "load_settings",
    "project_root",
    "selfcheck",
]


def selfcheck(*, strict: bool = True, config_path: str | Path | None = None) -> int:
    """导入自检：打印版本、配置路径、目录与环境变量状态。

    返回进程退出码：0 通过；2 配置/环境问题（可预期，不打印堆栈）。
    `strict=False` 时缺少密钥只告警不失败（供无需云端的 Step 使用）。
    """
    print(f"lit_agent_min {__version__}")
    print(f"python         {sys.version.split()[0]}")
    print(f"project_root   {project_root()}")

    try:
        settings = load_settings(config_path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2

    print(f"config         {settings.config_path}")
    created = ensure_dirs(settings)
    print(f"logs_dir       {settings.paths.logs_dir}")
    print(f"data_dir       {settings.paths.data_dir}")
    print(f"dirs_created   {len(created)}")
    print(f"cloud          {settings.providers.cloud.name} / {settings.providers.cloud.model}")
    if settings.providers.local is not None:
        local = settings.providers.local
        print(f"local          {local.engine} / {local.model} ({local.base_url})")
    print(
        f"guards         cosine_min={settings.guards.scope_cosine_min} "
        f"oos_max={settings.guards.oos_share_max} loop_k={settings.guards.loop_k}"
    )

    missing = missing_env(settings)
    if missing:
        if strict:
            print(f"[FAIL] 缺少环境变量：{'、'.join(missing)}", file=sys.stderr)
            try:
                ensure_env(settings)
            except ConfigError as exc:
                print(str(exc), file=sys.stderr)
            return 2
        print(f"[WARN] 缺少环境变量：{'、'.join(missing)}（--lax 模式继续）")

    print("[OK] selfcheck passed" + ("" if strict else " (lax)"))
    return 0
