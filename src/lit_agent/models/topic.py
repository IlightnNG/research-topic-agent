"""主题（topic）契约：scope statement 是"是否离题"的唯一判定依据。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from lit_agent.models._base import ContractModel

__all__ = ["Topic", "TopicSource", "TopicStatus"]


class TopicStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TopicSource(ContractModel):
    """抓取范围：一个 topic 在每个源上的一条 selector。"""

    source: str = Field(min_length=1, description="openalex | arxiv")
    selector: dict = Field(
        default_factory=dict,
        description="openalex: {venue_ids:[], from_year, type}；arxiv: {categories:[], from_year}",
    )


class Topic(ContractModel):
    id: str = Field(min_length=1, description="slug，如 'ai-agents'")
    name: str = Field(min_length=1)
    description: str = ""
    scope_statement: str = Field(min_length=1, description="范围唯一来源（守卫判 scope 用）")
    scope_keywords: list[str] = Field(default_factory=list)
    seed_queries: list[str] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.ACTIVE
    schedule_cron: str | None = Field(default=None, description="None = 不调度（Phase 1 恒 None）")
    sources: list[TopicSource] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
