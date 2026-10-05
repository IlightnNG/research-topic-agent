"""lit_agent_min —— Phase 0 最小可复用内核。

公开入口
- 配置：`load_settings()` / `ConfigError` / `ensure_dirs()` / `missing_env()`
- 契约：`Paper / EvidenceCard / Citation / Claim / Verdict / Event`（`models.py`）
- 事件：`JsonlEventLog` / `EventSink` / `read_events()`（`eventlog.py`）
- 日志：`setup_logging()` / `bind_context()` / `log_event()`（`logging.py`）
- 自检：`selfcheck()`（版本 → 配置 → 目录 → 密钥，返回进程退出码）
"""

from __future__ import annotations

import sys
from pathlib import Path

from ._version import __version__
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
from .eventlog import EventLogError, EventSink, JsonlEventLog, read_events
from .logging import (
    LoggingContractError,
    LoggingHandles,
    bind_context,
    clear_context,
    get_logger,
    log_event,
    setup_logging,
    validate_no_bodies,
)
from .models import (
    Author,
    Citation,
    Claim,
    Event,
    EventType,
    EvidenceCard,
    GuardAction,
    Paper,
    RunId,
    Severity,
    Support,
    Verdict,
)

__all__ = [
    # 配置
    "ConfigError",
    "Settings",
    "default_config_path",
    "ensure_dirs",
    "ensure_env",
    "load_settings",
    "missing_env",
    "open_event_log",
    "project_root",
    "selfcheck",
    # 契约
    "Author",
    "Citation",
    "Claim",
    "Event",
    "EventType",
    "EvidenceCard",
    "GuardAction",
    "Paper",
    "RunId",
    "Severity",
    "Support",
    "Verdict",
    # 事件
    "EventLogError",
    "EventSink",
    "JsonlEventLog",
    "read_events",
    # 日志
    "LoggingContractError",
    "LoggingHandles",
    "bind_context",
    "clear_context",
    "get_logger",
    "log_event",
    "setup_logging",
    "validate_no_bodies",
    # 元信息
    "__version__",
]


def open_event_log(
    path: str | Path | None = None, *, run_id: RunId, fsync: bool = False
) -> JsonlEventLog:
    """按配置创建事件日志；默认写到 `<out_dir>/events.jsonl`。

    供各 Step 统一入口使用：既保证事件落点一致，也让 Phase 1 替换 sink 时只改这一处。
    """
    settings = load_settings()
    target = Path(path).expanduser() if path else settings.paths.out_dir / "events.jsonl"
    return JsonlEventLog(target, run_id=run_id, fsync=fsync)


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
