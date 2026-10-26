"""Phase 3.1 / S4：面向用户的 API 文案（默认英文，zh 可选）。

只翻译“错误响应”的 message，不翻译事件、日志与报告正文。
"""

from __future__ import annotations

from typing import Literal

__all__ = ["Locale", "resolve_locale", "translate_error"]

Locale = Literal["en", "zh"]

ERROR_MESSAGES: dict[str, dict[Locale, str]] = {
    "E_NOT_FOUND": {"en": "Resource not found.", "zh": "资源不存在。"},
    "E_LOCK_HELD": {"en": "This topic already has a running job.", "zh": "该 topic 已有任务在运行。"},
    "E_FEATURE_DISABLED": {"en": "This feature is not available yet.", "zh": "该功能尚未开放。"},
    "E_CONFIG_INVALID": {"en": "Invalid configuration.", "zh": "配置不合法。"},
    "E_SRC_TIMEOUT": {"en": "The data source timed out. Try again later.", "zh": "数据源响应超时，可稍后重试。"},
    "E_SRC_AUTH": {"en": "Data source quota exhausted or API key missing.", "zh": "数据源配额用尽或缺少 API key。"},
    "E_SRC_NO_SELECTOR": {"en": "This topic has no data source selector.", "zh": "该 topic 未配置数据源 selector。"},
    "E_BUDGET_COST": {"en": "Run budget exhausted.", "zh": "本次预算已用尽。"},
    "E_RUN_ABORTED": {"en": "The run was aborted.", "zh": "本次运行已被中止。"},
    "E_PERMISSION_REQUIRED": {"en": "This action requires approval.", "zh": "该操作需要确认。"},
    "E_GUARD_STAGNATION": {"en": "No new progress; continuing in degraded mode.", "zh": "连续无新增，已降级继续。"},
    "E_UNEXPECTED": {"en": "Unexpected error.", "zh": "发生了意外错误。"},
}


def resolve_locale(accept_language: str | None) -> Locale:
    value = (accept_language or "").lower()
    return "zh" if value.startswith("zh") else "en"


def translate_error(code: str, locale: Locale, *, fallback: str | None = None) -> str:
    table = ERROR_MESSAGES.get(code)
    if table is not None:
        return table[locale]
    return fallback or code
