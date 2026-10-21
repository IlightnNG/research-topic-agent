"""条件边（S3）：E1–E13 的判定与路由。

约定
- **纯函数**：只读 `state`，不写库、不发事件（事件由 graph_runner 发）；
- 一条边 = 一个**谓词** + 一个**动作**；`route_after` 按优先级取最重的动作；
- 每个动作对应一个目标：`abort` / `replan` / `retry` / `degrade` / `skip` / `annotate` / `expand` / `rewrite` / `warn`。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lit_agent.errors import E_FEATURE_DISABLED, LitError

__all__ = [
    "EDGES",
    "MAINLINE",
    "PRIORITY",
    "RULES",
    "EdgeRule",
    "backoff_edge",
    "evaluate_edges",
    "route_after",
]

#: E1–E13（编号与 design 文档一致；contract 测试会比对）
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

#: 十节点主干（S2 落地）
MAINLINE: tuple[str, ...] = (
    "intake",
    "scope",
    "retrieval",
    "parse",
    "normalize",
    "mapping",
    "analysis",
    "critique",
    "report",
    "evaluate",
)

#: 动作优先级（数字越大越重）
PRIORITY: dict[str, int] = {
    "annotate": 1,
    "warn": 2,
    "skip": 3,
    "degrade": 4,
    "retry": 5,
    "rewrite": 5,
    "expand": 5,
    "replan": 6,
    "abort": 7,
}

Predicate = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class EdgeRule:
    edge: str
    stage: str
    action: str
    predicate: Predicate
    note: str


def _has(state: dict[str, Any], name: str) -> bool:
    """该阶段是否已经写入了这个计数（用于区分\"没跑\"与\"跑了但为 0\"）。"""
    return name in (state.get("counters") or {})


def _counter(state: dict[str, Any], name: str) -> int:
    counters = state.get("counters") or {}
    try:
        return int(counters.get(name, 0))
    except (TypeError, ValueError):
        return 0


#: E1–E13 的具体判定（每条边都必须有规则，否则 S3 不算完成）
RULES: tuple[EdgeRule, ...] = (
    EdgeRule("E1", "scope", "annotate", lambda s: _counter(s, "drift_warn") > 0, "补 scope 提示"),
    EdgeRule("E2", "scope", "abort", lambda s: _counter(s, "drift_block") > 0, "漂移阻断"),
    EdgeRule("E3", "retrieval", "retry", lambda s: _counter(s, "retrieval_errors") > 0, "检索退避重试"),
    EdgeRule(
        "E4",
        "retrieval",
        "degrade",
        lambda s: _has(s, "new_papers") and _counter(s, "new_papers") == 0,
        "零新增降级",
    ),
    EdgeRule("E5", "parse", "skip", lambda s: _counter(s, "parse_failed") > 0, "跳过坏 PDF"),
    EdgeRule("E6", "normalize", "retry", lambda s: _counter(s, "schema_errors") > 0, "schema 失败重试"),
    EdgeRule(
        "E7",
        "mapping",
        "expand",
        lambda s: _has(s, "cards") and _counter(s, "cards") == 0,
        "证据不足扩检索",
    ),
    EdgeRule("E8", "analysis", "degrade", lambda s: _counter(s, "no_progress") >= 2, "无进展降级"),
    EdgeRule("E9", "analysis", "rewrite", lambda s: _counter(s, "unresolved_citations") > 0, "重写 claim"),
    EdgeRule("E10", "evaluate", "warn", lambda s: _counter(s, "eval_below") > 0, "评测不达标告警"),
    EdgeRule("E11", "critique", "replan", lambda s: _counter(s, "loop") > 0, "循环/停滞 replan"),
    EdgeRule("E12", "*", "abort", lambda s: _counter(s, "budget_stop") > 0, "预算超限终止"),
    EdgeRule("E13", "evaluate", "degrade", lambda s: _counter(s, "retries_exhausted") > 0, "低置信收尾"),
)


def evaluate_edges(state: dict[str, Any], stage: str) -> list[EdgeRule]:
    """返回当前 stage 上**命中**的边（E12 为任意阶段）。"""
    fired: list[EdgeRule] = []
    for rule in RULES:
        if rule.stage not in (stage, "*"):
            continue
        try:
            if rule.predicate(state):
                fired.append(rule)
        except Exception:  # noqa: BLE001 - 谓词异常视为"不触发"，由上层观测
            continue
    return fired


def route_after(stage: str, state: dict[str, Any]) -> str:
    """返回下一跳：动作名（abort/replan/retry/...）或下一阶段名或 `end`。"""
    fired = evaluate_edges(state, stage)
    if fired:
        return max(fired, key=lambda rule: PRIORITY[rule.action]).action
    if stage in MAINLINE:
        index = MAINLINE.index(stage)
        return MAINLINE[index + 1] if index + 1 < len(MAINLINE) else "end"
    raise LitError(
        E_FEATURE_DISABLED,
        f"未知阶段 {stage!r}（不在十节点主干内）",
        context={"stage": stage, "mainline": list(MAINLINE)},
    )


def backoff_edge(edge: str) -> str:
    """返回该边的动作（E1–E13 全部已实现，S3 起不再抛"未实现"）。"""
    for rule in RULES:
        if rule.edge == edge:
            return rule.action
    raise ValueError(f"未知边：{edge}")
