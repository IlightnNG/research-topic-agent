"""作者契约（P4 的"作者动向"以此为主键做聚合）。"""

from __future__ import annotations

from pydantic import Field

from lit_agent.models._base import ContractModel

__all__ = ["Author"]


class Author(ContractModel):
    author_id: str = Field(min_length=1, description="稳定键：源内 author id 或 name_norm 派生")
    name: str = Field(min_length=1)
    name_norm: str = Field(min_length=1, description="归一化名（消歧预留，本轮不做消歧）")
