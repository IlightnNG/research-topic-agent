"""事件契约（guide §2.2 + ADR-0005 §5–§6）。

Phase 0 落 JSONL；Phase 1 落 SQLite `run_events`，本模型是两边共用的唯一结构定义。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, ValidationError, field_validator

from lit_agent.models._base import ContractModel, RunId, Severity, format_validation

__all__ = ["Event", "EventType"]


class EventType(StrEnum):
    """事件类型（契约固定分类，见 guide §2.2 白名单）。"""

    PHASE_CHANGE = "phase_change"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    GUARD_TRIGGER = "guard_trigger"
    RECOVERY = "recovery"
    MESSAGE = "message"
    ERROR = "error"
    METRIC = "metric"
    REPORT_WRITTEN = "report_written"


class Event(ContractModel):
    """事件真相源的一行。`dedupe_key` 为 NULL 表示"非幂等事件"（不参与去重）。"""

    id: int | None = Field(default=None, description="全局主键，由数据库分配")
    run_id: RunId
    seq: int = Field(ge=1, description="同一 run 内单调递增（runs.next_seq 分配）")
    ts: datetime = Field(description="UTC，必须带时区")
    type: EventType
    stage: str | None = None
    agent: str | None = None
    severity: Severity = Severity.INFO
    dedupe_key: str | None = Field(
        default=None, description="'<stage>:<step_key>'，仅幂等操作用；非幂等事件必须为 None"
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default="1.0", min_length=1)

    @field_validator("run_id")
    @classmethod
    def _run_id_not_empty(cls, value: RunId) -> RunId:
        if isinstance(value, str) and not value.strip():
            raise ValueError("run_id 不得为空字符串")
        return value

    @field_validator("ts")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ts 必须带时区（UTC），例如 2026-01-01T03:00:00Z")
        return value.astimezone(UTC)

    @field_validator("dedupe_key")
    @classmethod
    def _dedupe_key_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("dedupe_key 不得为空字符串（非幂等事件请用 None）")
        if ":" not in value:
            raise ValueError("dedupe_key 必须是 '<stage>:<step_key>' 形式")
        return value

    @field_validator("payload")
    @classmethod
    def _json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload 必须可 JSON 序列化：{exc}") from None
        return value

    def to_json_line(self) -> str:
        """单行 JSON（不含换行符），供 JSONL 导出与测试使用。"""
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json_line(cls, line: str) -> Event:
        try:
            return cls.model_validate_json(line)
        except ValidationError as exc:
            raise ValueError(f"事件行不符合契约：{format_validation(exc)}") from None
