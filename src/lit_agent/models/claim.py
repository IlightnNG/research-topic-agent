"""断言（claim）契约：不可落地的断言也必须能入库（Phase 0 静默错误 #6 的反面）。"""

from __future__ import annotations

from pydantic import Field, model_validator

from lit_agent.models._base import ContractModel
from lit_agent.models.evidence import Citation, Support

__all__ = ["Claim"]


class Claim(ContractModel):
    text: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    support: Support = Support.UNVERIFIED
    # --- ADR-0005 增量 ---
    claim_id: str | None = Field(default=None, description="'<run_id>:<短 hash>'，入库时分配")
    text_sha: str | None = Field(default=None, description="sha256(规范化 text)，幂等键")
    report_id: str | None = None

    @model_validator(mode="after")
    def _require_evidence(self) -> Claim:
        # 只有"正面断言"必须带证据；`unsupported` / `unverified` 允许无引用——
        # 否则"无法落地的 claim"只能被丢弃，而丢弃会伪造 grounding=100%（Phase 0 #6）。
        if self.support in (Support.SUPPORTED, Support.CONTRADICTED) and not self.citations:
            raise ValueError("supported/contradicted 的 claim 必须至少带 1 条 citation")
        return self
