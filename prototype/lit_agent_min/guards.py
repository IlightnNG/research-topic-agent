"""守卫（Guards）：G1 漂移 / G4 循环与停滞 / 预算看门狗 + 恢复包。

职责边界
- 守卫是**纯判定**：吃"观测值"，吐结构化 `Verdict`（`models.Verdict`），**不写事件、不改状态、不调 LLM**。
  写事件与执行处置由编排层（steps/ 或未来的 graph 节点）负责——这样守卫可单测、可复现、可离线跑。
- 判定优先用**确定性打分**，绝不用 LLM 判守卫（设计原则：能被结构约束的不写进提示词）。

关于"embedding"的实测取舍（S6 标定的核心）
- spec 写的是 `cos(embed(产物), embed(scope))`，但本轮**没有本地 embedding 模型**（bge-m3 未就位、网络受限）。
- 因此默认打分器是**词法 TF-IDF 余弦**（与 S5 检索同源、确定性、可离线）。
- ⚠️ **阈值必须按打分器重新标定**：配置里的 0.60/0.45 是按 embedding 余弦给的，
  而 S5 实测同主题论文的词法余弦只有 0.038–0.134 —— 直接套用会把**全部正常样本判为漂移**。
  本模块因此同时提供两种阈值口径：
    ① `drift_warn` / `drift_block`：绝对阈值（配置来源，可被标定覆盖）；
    ② `relative_percentile`：相对口径（当前观测在历史分布中的分位），对打分器量纲不敏感。
  实际判定 = 两者取更宽松者（先保证零误报，再谈召回），标定过程与结果见 `RESULTS.md` §2.13。

升级阶梯（与 `design/state-machine-and-guards.md` §8 一致）
`retry → degrade → replan → abort(annotate)`；同一 run 内 G4 第二次命中即升级到终止。
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .models import GuardAction, Severity, Verdict

__all__ = [
    "BudgetWatchdog",
    "DriftGuard",
    "GuardRail",
    "LoopGuard",
    "ProgressGuard",
    "build_recovery_packet",
    "signature",
]

Scorer = Callable[[str], float]
"""打分器签名：产物文本 -> 与 scope 的相似度（越大越相关）。

为什么不是 `(text, scope)`：scope 的**表示**既可以是关键词串，也可以是**种子语料质心**
（S6 实测证明只有质心表示才让正/负样本可分）。把"怎么算分"交给调用方，守卫只负责阈值与判决。
"""


def signature(tool: str, params: dict[str, Any]) -> str:
    """工具调用签名 = 工具名 + 参数哈希（G4 的最小可判据）。

    参数做**规范化序列化**（排序键、忽略顺序），保证"同一次语义调用"得到同一签名。
    """
    blob = json.dumps(
        params, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return f"{tool}:{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


# --------------------------------------------------------------------------- #
# G1 漂移守卫
# --------------------------------------------------------------------------- #
@dataclass
class DriftGuard:
    """G1：阶段产物与 scope 的相似度过低 → warn / block（回退检索 + 注入恢复包）。"""

    scorer: Scorer
    drift_warn: float
    drift_block: float
    scope_label: str = ""
    """scope 的可读标签（写事件用，不参与判定）。"""
    relative_percentile: float = 0.0
    """>0 时启用相对口径：低于历史分布的第 p 分位才算漂移。"""

    history: list[float] = field(default_factory=list)
    code: str = "E_GUARD_DRIFT"

    def observe(self, text: str) -> float:
        """打分并记入历史分布（历史只用于分位口径，不参与绝对阈值）。"""
        score = float(self.scorer(text))
        self.history.append(score)
        return score

    def _percentile_threshold(self) -> float | None:
        if self.relative_percentile <= 0 or len(self.history) < 5:
            return None
        ordered = sorted(self.history)
        idx = max(0, min(len(ordered) - 1, int(self.relative_percentile * len(ordered))))
        return ordered[idx]

    def check(self, text: str) -> tuple[Verdict, float]:
        """返回 (判决, 本次相似度)。**绝对阈值与相对阈值取更宽松者**（先保零误报）。"""
        score = self.observe(text)
        relative = self._percentile_threshold()
        effective_block = self.drift_block if relative is None else min(self.drift_block, relative)
        effective_warn = self.drift_warn if relative is None else min(self.drift_warn, relative)
        reasons = [
            f"相似度={score:.4f}",
            f"阈值(warn/block)={effective_warn:.4f}/{effective_block:.4f}",
            "打分器=lexical_tfidf",
        ]
        if relative is not None:
            reasons.append(f"相对分位阈值(p={self.relative_percentile})={relative:.4f}")
        if score < effective_block:
            return (
                Verdict(
                    ok=False,
                    severity=Severity.ERROR,
                    action=GuardAction.REPLAN,
                    code=self.code,
                    reasons=[*reasons, "低于 block 阈值 → 回退检索并注入恢复包"],
                ),
                score,
            )
        if score < effective_warn:
            return (
                Verdict(
                    ok=False,
                    severity=Severity.WARNING,
                    action=GuardAction.RETRY,
                    code=self.code,
                    reasons=[*reasons, "低于 warn 阈值 → 带恢复包重试本阶段"],
                ),
                score,
            )
        return Verdict(
            ok=True, action=GuardAction.CONTINUE, code="OK_DRIFT", reasons=reasons
        ), score


# --------------------------------------------------------------------------- #
# G4 循环守卫 / 停滞守卫
# --------------------------------------------------------------------------- #
@dataclass
class LoopGuard:
    """G4：工具调用签名在窗口 k 内成环 → replan；再次命中 → abort(annotate)。"""

    window: int = 5
    repeat_threshold: int = 3
    """同一签名在窗口内出现次数达到该值即判成环。"""
    code: str = "E_GUARD_LOOP"

    calls: deque[str] = field(default_factory=lambda: deque(maxlen=64))
    hits: int = 0

    def record(self, tool: str, params: dict[str, Any]) -> str:
        sig = signature(tool, params)
        self.calls.append(sig)
        return sig

    def check(self) -> Verdict:
        recent = list(self.calls)[-self.window :]
        if not recent:
            return Verdict(ok=True, code="OK_LOOP", reasons=["窗口内无调用"])
        counts = Counter(recent)
        sig, count = counts.most_common(1)[0]
        reasons = [
            f"窗口 k={self.window} 内重复签名 {count} 次（阈值 {self.repeat_threshold}）",
            f"重复签名={sig}",
            f"窗口内序列={recent}",
        ]
        if count < self.repeat_threshold:
            return Verdict(ok=True, code="OK_LOOP", reasons=reasons)
        self.hits += 1
        if self.hits == 1:
            return Verdict(
                ok=False,
                severity=Severity.WARNING,
                action=GuardAction.REPLAN,
                code=self.code,
                reasons=[*reasons, "首次成环 → 强制 replan（清空本轮查询并换策略）"],
            )
        return Verdict(
            ok=False,
            severity=Severity.ERROR,
            action=GuardAction.ABORT,
            code=self.code,
            reasons=[*reasons, "再次成环 → 终止本 run 并 annotate（不再空转消耗预算）"],
        )


@dataclass
class ProgressGuard:
    """停滞守卫：连续 `no_progress_steps` 步没有新增条目（检索空转/无效重试）→ replan / abort。"""

    no_progress_steps: int = 2
    code: str = "E_GUARD_STAGNATION"

    streak: int = 0
    hits: int = 0

    def update(self, new_items: int) -> Verdict:
        if new_items > 0:
            self.streak = 0
            return Verdict(
                ok=True, code="OK_PROGRESS", reasons=[f"本步新增 {new_items} 条，停滞计数清零"]
            )
        self.streak += 1
        reasons = [
            f"本步新增 0 条，连续停滞 {self.streak} 步（阈值 {self.no_progress_steps}）",
        ]
        if self.streak < self.no_progress_steps:
            return Verdict(ok=True, code="OK_PROGRESS", reasons=reasons)
        self.hits += 1
        if self.hits == 1:
            return Verdict(
                ok=False,
                severity=Severity.WARNING,
                action=GuardAction.DEGRADE,
                code=self.code,
                reasons=[*reasons, "首次停滞 → 降级换源（换查询/换通道）后重试"],
            )
        return Verdict(
            ok=False,
            severity=Severity.ERROR,
            action=GuardAction.ABORT,
            code=self.code,
            reasons=[*reasons, "持续停滞 → 终止并 annotate（避免无效周更）"],
        )


# --------------------------------------------------------------------------- #
# 预算看门狗
# --------------------------------------------------------------------------- #
@dataclass
class BudgetWatchdog:
    """run 级预算：token / 时长 / 成本 / 步数；80% warn、100% stop（与 spec 一致）。"""

    max_tokens: int | None = None
    max_seconds: float | None = None
    max_usd: float | None = None
    max_steps: int | None = None
    warn_ratio: float = 0.8
    code: str = "E_BUDGET_EXCEEDED"
    warn_code: str = "W_BUDGET_NEAR_LIMIT"

    tokens: int = 0
    seconds: float = 0.0
    cost_usd: float = 0.0
    steps: int = 0

    def add(
        self,
        *,
        tokens: int = 0,
        seconds: float = 0.0,
        cost_usd: float = 0.0,
        steps: int = 1,
    ) -> None:
        self.tokens += max(0, tokens)
        self.seconds += max(0.0, seconds)
        self.cost_usd += max(0.0, cost_usd)
        self.steps += max(0, steps)

    def usage(self) -> dict[str, Any]:
        def ratio(used: float, cap: float | None) -> float | None:
            return None if not cap else round(used / cap, 4)

        return {
            "tokens": self.tokens,
            "tokens_ratio": ratio(self.tokens, self.max_tokens),
            "seconds": round(self.seconds, 3),
            "seconds_ratio": ratio(self.seconds, self.max_seconds),
            "cost_usd": round(self.cost_usd, 6),
            "cost_ratio": ratio(self.cost_usd, self.max_usd),
            "steps": self.steps,
            "steps_ratio": ratio(self.steps, self.max_steps),
        }

    def check(self) -> Verdict:
        """任一维度达到 100% → stop；达到 80% → warn（warn 不阻断，只记账 + 提示）。"""
        usage = self.usage()
        breached = [
            k for k, v in usage.items() if k.endswith("_ratio") and v is not None and v >= 1.0
        ]
        near = [
            k
            for k, v in usage.items()
            if k.endswith("_ratio") and v is not None and self.warn_ratio <= v < 1.0
        ]
        reasons = [f"{k}={usage[k]:.3f}" for k in [*breached, *near]]
        if breached:
            return Verdict(
                ok=False,
                severity=Severity.ERROR,
                action=GuardAction.ABORT,
                code=self.code,
                reasons=[
                    f"预算超限：{', '.join(breached)}",
                    *reasons,
                    "立即停止本 run 并 annotate",
                ],
            )
        if near:
            return Verdict(
                ok=False,
                severity=Severity.WARNING,
                action=GuardAction.CONTINUE,
                code=self.warn_code,
                reasons=[f"接近预算上限（≥{self.warn_ratio:.0%}）：{', '.join(near)}", *reasons],
            )
        return Verdict(
            ok=True,
            action=GuardAction.CONTINUE,
            code="OK_BUDGET",
            reasons=reasons or ["未设置上限"],
        )


# --------------------------------------------------------------------------- #
# 恢复包（Recovery Packet）
# --------------------------------------------------------------------------- #
def build_recovery_packet(
    *,
    verdict: Verdict,
    stage: str,
    trusted_state: dict[str, Any],
    next_constraints: Sequence[str],
    attempt: int,
    history: Iterable[str] = (),
) -> dict[str, Any]:
    """把"失败原因 + 可信状态 + 下一步约束"打包成可注入上下文的最小结构（spec §9 的收敛版）。"""
    return {
        "guard": {
            "code": verdict.code,
            "action": str(verdict.action),
            "severity": str(verdict.severity),
        },
        "failure": {"stage": stage, "attempt": attempt, "reasons": list(verdict.reasons)},
        "trusted_state": trusted_state,
        "next_constraints": list(next_constraints),
        "recent_actions": list(history)[-5:],
    }


@dataclass
class GuardRail:
    """把三类守卫 + 看门狗挂在一起，供编排层一次调用（只判定，不改状态、不写事件）。"""

    drift: DriftGuard
    loop: LoopGuard
    progress: ProgressGuard
    budget: BudgetWatchdog

    def check_all(
        self,
        *,
        product_text: str | None = None,
        new_items: int | None = None,
    ) -> list[Verdict]:
        """按需触发各守卫；`product_text`/`new_items` 为 None 表示本步不做该项判定。"""
        verdicts: list[Verdict] = []
        if product_text is not None:
            verdict, _score = self.drift.check(product_text)
            verdicts.append(verdict)
        verdicts.append(self.loop.check())
        if new_items is not None:
            verdicts.append(self.progress.update(new_items))
        verdicts.append(self.budget.check())
        return verdicts
