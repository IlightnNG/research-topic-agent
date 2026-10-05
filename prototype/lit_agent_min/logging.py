"""结构化日志（Step 0.3 最小基线）——Phase 0 的"过程可读"层。

规范：`docs/implementation/logging-and-observability.md`
- §2.1 字段字典：必填 `ts/level/event/logger/msg/app_version/config_version/host/pid/schema_version`
- §3 级别与脱敏：info 以上不含正文；密钥/邮箱/家目录路径统一脱敏
- §4 落盘：`logs/app.jsonl`（全量）+ `logs/errors.jsonl`（仅 error/critical）
- §9 查看：`validate_no_bodies()` 供测试/CI 扫描 info 行是否混入正文

设计要点
- **双写纪律**：外部调用（源 API / LLM / DB）必须"一条日志 + 一条事件"；本模块只管日志，
  事件由 `eventlog.py` 负责，两者用 `run_id + stage` 关联（见 `bind_context`）。
- **日志不得拖垮业务**：脱敏与正文守卫在异常时降级为占位符，绝不抛异常（契约违规除外，
  由 `log_event` 在严格模式下显式报错）。
- **可替换**：对外只暴露 `setup_logging / get_logger / bind_context / log_event`，
  Phase 1 换 structlog 之外的实现或加 OTel 时不影响调用方。
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import socket
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter

from ._version import __version__
from .config import Settings, load_settings
from .models import Severity

__all__ = [
    "LoggingContractError",
    "LoggingHandles",
    "bind_context",
    "clear_context",
    "get_logger",
    "log_event",
    "setup_logging",
    "validate_no_bodies",
]

SCHEMA_VERSION = "1.0"

_SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|credential)")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_SECRET_VALUE_RE = re.compile(r"\b(sk-[A-Za-z0-9._-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})")

#: 由 setup_logging 注入的静态字段（供 processor 读取）
_STATIC: dict[str, Any] = {
    "app_version": __version__,
    "config_version": "cfg-unknown",
    "host": "unknown",
    "pid": 0,
    "max_field_chars": 500,
    "strict_contracts": True,
    "configured": False,
}

_HANDLES: LoggingHandles | None = None


class LoggingContractError(RuntimeError):
    """日志契约违规（如 ERROR 级缺 `error_code`）——属编程错误，严格模式下显式报错。"""


@dataclass(frozen=True)
class LoggingHandles:
    app_log: Path
    error_log: Path
    level: str
    console: bool


# --------------------------------------------------------------------------- #
# processors
# --------------------------------------------------------------------------- #
def _inject_static(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in ("app_version", "config_version", "host", "pid"):
        event_dict.setdefault(key, _STATIC[key])
    event_dict.setdefault("schema_version", SCHEMA_VERSION)
    return event_dict


def _mask(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """密钥/邮箱/家目录路径脱敏（规范 §3）。异常时降级为占位符，绝不抛出。"""
    try:
        home = str(Path.home())
        for key, value in list(event_dict.items()):
            if not isinstance(value, str) or not value:
                continue
            if _SECRET_KEY_RE.search(key):
                event_dict[key] = "***"
                continue
            masked = _EMAIL_RE.sub(lambda m: f"{m.group(1)[0]}***@{m.group(2)}", value)
            masked = _SECRET_VALUE_RE.sub("***", masked)
            if home and home in masked:
                masked = masked.replace(home, "~")
            event_dict[key] = masked
    except Exception:  # noqa: BLE001 - 日志自身不得因脱敏失败而中断
        event_dict["_mask_error"] = True
    return event_dict


def _guard_body(_logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """正文守卫：info 及以上不得携带超长文本（规范 §3），超限字段替换为摘要。"""
    if method_name.lower() == "debug":
        return event_dict
    limit = int(_STATIC.get("max_field_chars", 500))
    try:
        for key, value in list(event_dict.items()):
            if isinstance(value, str) and len(value) > limit:
                digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
                event_dict[key] = f"<redacted chars={len(value)} sha1={digest}>"
    except Exception:  # noqa: BLE001
        event_dict["_guard_error"] = True
    return event_dict


def _shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        _inject_static,
        _mask,
        _guard_body,
        structlog.processors.format_exc_info,
    ]


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #
def config_version(settings: Settings) -> str:
    """配置版本：对影响行为的关键配置做短哈希，便于复现与对比实验。"""
    import json

    payload = json.dumps(
        {
            "providers": settings.providers.model_dump(mode="json"),
            "guards": settings.guards.model_dump(mode="json"),
            "logging": settings.logging.model_dump(mode="json"),
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return "cfg-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def setup_logging(
    settings: Settings | None = None,
    *,
    app_version: str = __version__,
    force: bool = False,
) -> LoggingHandles:
    """配置进程级日志（幂等）。

    落盘：`<logging.app_log>`（全量）+ `<logging.error_log>`（仅 error/critical）；
    控制台输出由 `logging.console` 控制。重复调用会重新绑定 handler（供测试用临时目录）。
    """
    global _HANDLES
    resolved = settings or load_settings()
    cfg = resolved.logging

    if _HANDLES is not None and not force:
        return _HANDLES

    _STATIC.update(
        {
            "app_version": app_version,
            "config_version": config_version(resolved),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "max_field_chars": cfg.max_field_chars,
            "strict_contracts": cfg.strict_contracts,
        }
    )

    shared = _shared_processors()
    formatter = ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=False,
    )

    level = getattr(logging, str(cfg.level).upper(), logging.INFO)
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)

    for path, handler_level in ((cfg.app_log, level), (cfg.error_log, logging.ERROR)):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(formatter)
        handler.setLevel(handler_level)
        root.addHandler(handler)

    if cfg.console:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        stream.setLevel(level)
        root.addHandler(stream)

    _STATIC["configured"] = True
    _HANDLES = LoggingHandles(
        app_log=Path(cfg.app_log),
        error_log=Path(cfg.error_log),
        level=cfg.level,
        console=cfg.console,
    )
    return _HANDLES


def get_logger(name: str = "lit_agent") -> BoundLogger:
    """取 logger；建议传 `__name__`。使用前需先 `setup_logging()`。"""
    if not _STATIC["configured"]:
        setup_logging()
    return structlog.get_logger(name)


# --------------------------------------------------------------------------- #
# 上下文与调用入口
# --------------------------------------------------------------------------- #
def bind_context(**fields: Any) -> None:
    """绑定随调用自动携带的上下文字段（run_id / stage / agent / attempt / topic_id …）。"""
    structlog.contextvars.bind_contextvars(**fields)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


def log_event(
    severity: Severity | str,
    event: str,
    msg: str = "",
    *,
    logger: str | None = None,
    **fields: Any,
) -> None:
    """按契约记录一条日志。

    - `event`：语义事件名（snake_case，必填）；`msg`：一行人类可读描述。
    - `severity`：见 `models.Severity`；ERROR/CRITICAL 必须带 `error_code`（严格模式下报错）。
    """
    if not event:
        raise LoggingContractError("必须提供语义事件名 event（snake_case）")
    level = severity if isinstance(severity, Severity) else Severity(str(severity))
    if (
        level in (Severity.ERROR, Severity.CRITICAL)
        and not fields.get("error_code")
        and _STATIC.get("strict_contracts", True)
    ):
        raise LoggingContractError(
            f"ERROR/CRITICAL 日志必须带 error_code（event={event}，见 errors.py 错误分类学）"
        )
    log = get_logger(logger or "lit_agent")
    # structlog 的 bound logger 方法签名为 (event=None, **kw)：用关键字显式区分语义名与人类可读 msg。
    getattr(log, level.value)(event=event, msg=msg, **fields)


# --------------------------------------------------------------------------- #
# 校验工具（测试 / CI）
# --------------------------------------------------------------------------- #
def validate_no_bodies(lines: Iterable[str], *, max_len: int = 500) -> list[str]:
    """扫描 JSONL 日志行，返回疑似混入正文的行（供 CI 断言 info 行无正文）。

    判定：info 及以上级别出现长度 > `max_len` 的字符串字段。
    """
    import json

    violations: list[str] = []
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            violations.append(f"line {lineno}: 非法 JSON")
            continue
        if str(record.get("level", "info")).lower() == "debug":
            continue
        for key, value in record.items():
            if isinstance(value, str) and len(value) > max_len:
                violations.append(f"line {lineno}: 字段 {key} 长度 {len(value)} > {max_len}")
    return violations
