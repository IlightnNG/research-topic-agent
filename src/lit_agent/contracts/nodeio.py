"""NodeIO 契约（Phase 2.1 / S2）。

只约束**边界**：节点返回什么形状、门禁判决长什么样；
不约束节点内部如何推理（否则 ReAct 写不出来）。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Decision", "GateResult", "NodeOutput", "PendingWrite"]

Action = Literal["continue", "annotate", "retry", "repair", "degrade", "replan", "abort"]
WriteKind = Literal["report", "metrics"]


class PendingWrite(BaseModel):
    """声明式写入：门禁通过后由 `runtime/commit.py` 执行。"""

    model_config = ConfigDict(extra="forbid")

    kind: WriteKind


class GateResult(BaseModel):
    """一条门禁判决（ok=False 才算失败）。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    ok: bool
    code: str = "E_OK"
    action: Action = "continue"
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class NodeOutput(BaseModel):
    """节点返回值的最小形状（校验用；允许额外字段）。"""

    model_config = ConfigDict(extra="allow")

    stage: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    counters: dict[str, Any] = Field(default_factory=dict)
    pending_writes: list[PendingWrite] = Field(default_factory=list)


class Decision(BaseModel):
    """监督者决策：只产出，不执行；执行器（runner）与边都读它。"""

    model_config = ConfigDict(extra="forbid")

    action: Action
    target: str | None = None
    code: str = "E_OK"
    reasons: list[str] = Field(default_factory=list)
    source: Literal["gate", "guard", "llm", "none"] = "none"
    attempt: int = 0
    drop_claim_indexes: list[int] = Field(default_factory=list)
    deferred: bool = False
