"""节点契约规格（S11）：十节点的"边界声明"，不约束内部实现。

每条 spec 声明：版本、门禁、副作用、最大尝试次数、幂等键模板。
契约测试（`tests/contracts/test_node_specs.py`）据此**自动生成** 6 条通用断言。
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ALLOWED_SIDE_EFFECTS", "SPECS", "NodeSpec", "spec_for"]

ALLOWED_SIDE_EFFECTS = {"reports", "claims", "metrics", "events"}


@dataclass(frozen=True)
class NodeSpec:
    name: str
    version: str = "1.0.0"
    gates: tuple[str, ...] = ("schema",)
    side_effects: tuple[str, ...] = ()
    max_attempts: int = 1
    idempotency: str = "{run_id}:{stage}:{attempt}"
    budget_usd: float = 0.0
    notes: str = field(default="", compare=False)


def _spec(name: str, gates: tuple[str, ...], **kwargs: object) -> NodeSpec:
    return NodeSpec(name=name, gates=gates, **kwargs)  # type: ignore[arg-type]


SPECS: dict[str, NodeSpec] = {
    "intake": _spec("intake", ("schema",)),
    "scope": _spec("scope", ("schema",)),
    "retrieval": _spec("retrieval", ("schema", "evidence_sufficiency"), max_attempts=2),
    "parse": _spec("parse", ("schema",)),
    "normalize": _spec("normalize", ("schema",)),
    "mapping": _spec("mapping", ("schema",)),
    "analysis": _spec("analysis", ("schema", "citation_integrity"), max_attempts=2),
    "critique": _spec(
        "critique",
        ("schema", "citation_integrity", "support_ratio"),
        max_attempts=2,
    ),
    "report": _spec(
        "report",
        ("schema", "citation_integrity", "budget"),
        side_effects=("reports", "claims"),
    ),
    "evaluate": _spec("evaluate", ("schema", "budget"), side_effects=("metrics",)),
}


def spec_for(name: str) -> NodeSpec:
    return SPECS[name]
