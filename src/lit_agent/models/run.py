"""运行（run）契约：状态机取值 + 事件序号分配器 + 输入漂移指纹。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from lit_agent.models._base import ContractModel

__all__ = ["Run", "RunState", "RunTrigger"]


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    RETRY = "retry"


class RunState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"
    PAUSED = "paused"


class Run(ContractModel):
    id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    trigger: RunTrigger = RunTrigger.MANUAL
    state: RunState = RunState.PENDING
    stage: str | None = Field(default=None, description="当前阶段")
    last_ok_stage: str | None = Field(default=None, description="最后成功阶段（失败报告用）")
    error_code: str | None = None
    next_seq: int = Field(default=0, ge=0, description="事件序号分配器（ADR-0005 §5）")
    dup_events: int = Field(default=0, ge=0, description="幂等命中计数（ADR-0005 §6）")
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    input_hash: str = Field(default="", description="topic+config+since 的哈希（G15 输入漂移）")
    app_version: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
