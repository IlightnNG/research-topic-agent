"""API 请求/响应契约（与 `models/` 复用，不重复定义领域模型）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ErrorOut", "RunRequest", "TopicCreate", "TopicUpdate"]


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="slug，如 ai-agents")
    name: str = Field(min_length=1)
    description: str = ""
    scope_statement: str = Field(min_length=1)
    scope_keywords: list[str] = Field(default_factory=list)
    seed_queries: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(
        default_factory=list, description="[{source, selector}]，openalex 需 venue_ids"
    )


class TopicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    scope_statement: str | None = None
    scope_keywords: list[str] | None = None
    seed_queries: list[str] | None = None
    status: str | None = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    max_usd: float | None = Field(default=None, gt=0)
    focus_hint: str | None = Field(default=None, max_length=120, description="本次运行的子主题提示")
    wait: bool = Field(default=True, description="True=同步返回；False=立即 202 后台执行")


class ErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool = False
    action_taken: str = "none"
    context: dict[str, Any] = Field(default_factory=dict)
