"""NodeGoal（Phase 3.0 / S1）：节点从"实现"变成"声明"。

字段全部是 JSON 值，可序列化、可哈希、可被 `ShellSpec` 引用。
门禁合法性在 `validate()` 里懒校验（避免 contracts 反向依赖 graph）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

__all__ = ["AUTONOMY_LEVELS", "GOALS", "NodeGoal", "all_goals", "goal_for"]

Autonomy = Literal["L0", "L1", "L2", "L3"]
AUTONOMY_LEVELS: tuple[str, ...] = ("L0", "L1", "L2", "L3")

MAX_POSTCONDITIONS = 2
MAX_STEPS_LIMIT = 5


@dataclass(frozen=True)
class NodeGoal:
    name: str
    objective: str
    postconditions: tuple[str, ...]
    tools: tuple[str, ...] = ()
    max_steps: int = 1
    max_usd: float = 0.0
    autonomy: Autonomy = "L1"
    escalation: Literal["none", "on_gate_failure"] = "on_gate_failure"
    notes: str = field(default="", compare=False)

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeGoal:
        payload = dict(data)
        payload["postconditions"] = tuple(payload.get("postconditions") or ())
        payload["tools"] = tuple(payload.get("tools") or ())
        return cls(**payload)

    def validate(self) -> list[str]:
        from lit_agent.graph.gates import GATE_NAMES

        problems: list[str] = []
        if not self.postconditions:
            problems.append(f"{self.name}: postconditions 不能为空")
        if len(self.postconditions) > MAX_POSTCONDITIONS:
            problems.append(
                f"{self.name}: postconditions 最多 {MAX_POSTCONDITIONS} 条（当前 {len(self.postconditions)}）"
            )
        unknown = [gate for gate in self.postconditions if gate not in GATE_NAMES]
        if unknown:
            problems.append(f"{self.name}: 未知门禁 {unknown}（合法：{list(GATE_NAMES)}）")
        if self.autonomy not in AUTONOMY_LEVELS:
            problems.append(f"{self.name}: autonomy 必须是 {AUTONOMY_LEVELS}")
        if not 1 <= self.max_steps <= MAX_STEPS_LIMIT:
            problems.append(f"{self.name}: max_steps 必须在 1..{MAX_STEPS_LIMIT}")
        if self.max_usd < 0:
            problems.append(f"{self.name}: max_usd 不能为负")
        return problems


def _g(name: str, objective: str, gates: tuple[str, ...], **kwargs: Any) -> NodeGoal:
    return NodeGoal(name=name, objective=objective, postconditions=gates, **kwargs)


#: 十节点的默认 Goal（L0/L1；L2 只在 retrieval/analysis 上通过开关启用）
GOALS: dict[str, NodeGoal] = {
    "intake": _g("intake", "确认 topic 存在且可运行", ("schema",), autonomy="L0"),
    "scope": _g("scope", "确认本轮范围并算范围指纹", ("schema",), autonomy="L0"),
    "retrieval": _g(
        "retrieval",
        "找到 >=N 篇与 scope 相关、可引用的证据",
        ("evidence_sufficiency",),
        tools=("hybrid_search", "rewrite_query"),
        max_steps=2,
        max_usd=0.02,
        autonomy="L1",
    ),
    "parse": _g("parse", "统计解析状态并可选调用 PDF 工具", ("schema",), autonomy="L0"),
    "normalize": _g("normalize", "去重合并，产出唯一论文集", ("schema",), autonomy="L0"),
    "mapping": _g(
        "mapping",
        "建立论文簇与引用关系",
        ("schema",),
        tools=("cluster_papers",),
        autonomy="L1",
    ),
    "analysis": _g(
        "analysis",
        "抽取可引用结论，且每条 claim 有引用、支持率达标",
        ("citation_integrity", "support_ratio"),
        tools=("extract_claims", "verify_claim", "rewrite_claim"),
        max_steps=3,
        max_usd=0.05,
        autonomy="L1",
    ),
    "critique": _g(
        "critique",
        "对 claims 做结构自查",
        ("citation_integrity", "support_ratio"),
        autonomy="L0",
    ),
    "report": _g(
        "report",
        "按模板产出报告（引用完整）",
        ("citation_integrity",),
        autonomy="L1",
        notes="写操作：由 commit 层执行",
    ),
    "evaluate": _g("evaluate", "计算并落库指标", ("schema",), autonomy="L0"),
}


def goal_for(name: str) -> NodeGoal:
    return GOALS[name]


def all_goals() -> list[NodeGoal]:
    from lit_agent.graph.nodes import PHASE2_STAGES

    return [GOALS[name] for name in PHASE2_STAGES]
