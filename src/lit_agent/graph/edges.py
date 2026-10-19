"""条件边常量与路由表（guide §6 / design E1–E13）。

Phase 1 只实现**主干路由**；回退类边（drift/loop/stagnation）一律显式抛
`E_FEATURE_DISABLED`，避免"骨架里顺手实现一半"（Phase 2 铺全边）。
"""

from __future__ import annotations

from typing import Any

from lit_agent.errors import E_FEATURE_DISABLED, LitError

__all__ = ["EDGES", "MAINLINE", "backoff_edge", "route_after"]

#: E1–E13（contract 测试会解析 design 文档比对编号）
EDGES: dict[str, str] = {
    "E1": "S0 漂移 warn → 补 scope 提示",
    "E2": "S0 漂移 block → 终止（annotate）",
    "E3": "S2 检索失败 → 退避重试",
    "E4": "S2 零新增 → 降级查询",
    "E5": "S3 解析失败 → 跳过该论文",
    "E6": "S4 阶段输出 schema 失败 → 重试一次",
    "E7": "S5 证据不足 → 扩大检索",
    "E8": "S6 分析无进展 → degrade",
    "E9": "S7 引用不可解析 → 重写该 claim",
    "E10": "S8 评测不达标 → warn 收尾",
    "E11": "任意 循环/停滞 → 强制 replan",
    "E12": "任意 预算超限 → abort（annotate）",
    "E13": "S8 用尽 → 标注低置信收尾",
}

#: Phase 1 已接通的主干（S0–S9 的线性子集）
MAINLINE: tuple[str, ...] = ("intake", "retrieve", "draft")


def route_after(stage: str, state: dict[str, Any]) -> str:
    """主干路由：返回下一个节点名（`end` 表示收尾）。未知/回退类显式未实现。"""
    if stage in MAINLINE:
        index = MAINLINE.index(stage)
        return MAINLINE[index + 1] if index + 1 < len(MAINLINE) else "end"
    raise LitError(
        E_FEATURE_DISABLED,
        f"边 {stage!r} 的回退逻辑在 Phase 2 实现（见 design E1–E13）",
        context={"stage": stage, "keys": sorted(state)},
    )


def backoff_edge(edge: str) -> None:
    """回退类边在 Phase 2 实现（Phase 1 只保留常量与路由入口）。"""
    if edge not in EDGES:
        raise ValueError(f"未知边：{edge}")
    raise LitError(
        E_FEATURE_DISABLED, f"{edge}（{EDGES[edge]}）在 Phase 2 实现", context={"edge": edge}
    )
