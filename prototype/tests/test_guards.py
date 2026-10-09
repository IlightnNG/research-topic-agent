"""守卫单测（Phase 0 step 6：G1 漂移 / G4 循环 / 停滞 / 预算看门狗 / 恢复包）。

设计要求：守卫是纯判定 → 全部可离线单测，不触网、不依赖 LLM。
"""

from __future__ import annotations

from lit_agent_min.guards import (
    BudgetWatchdog,
    DriftGuard,
    GuardRail,
    LoopGuard,
    ProgressGuard,
    build_recovery_packet,
    signature,
)
from lit_agent_min.models import GuardAction, Severity


def ramp(score: float):
    """固定分数的打分器（把"打分"与"判定"解耦，便于精确测阈值行为）。"""

    def scorer(_text: str) -> float:
        return score

    return scorer


# ---- G1 漂移 ---- #
def test_drift_passes_when_score_above_warn() -> None:
    guard = DriftGuard(scorer=ramp(0.5), drift_warn=0.3, drift_block=0.2)
    verdict, score = guard.check("anything")
    assert verdict.ok and verdict.action is GuardAction.CONTINUE
    assert score == 0.5


def test_drift_warns_then_blocks() -> None:
    warn_guard = DriftGuard(scorer=ramp(0.25), drift_warn=0.3, drift_block=0.2)
    verdict, _ = warn_guard.check("t")
    assert not verdict.ok
    assert verdict.severity is Severity.WARNING
    assert verdict.action is GuardAction.RETRY
    assert verdict.code == "E_GUARD_DRIFT"

    block_guard = DriftGuard(scorer=ramp(0.1), drift_warn=0.3, drift_block=0.2)
    verdict, _ = block_guard.check("t")
    assert not verdict.ok
    assert verdict.severity is Severity.ERROR
    assert verdict.action is GuardAction.REPLAN


def test_drift_records_history() -> None:
    guard = DriftGuard(scorer=ramp(0.4), drift_warn=0.3, drift_block=0.2)
    for _ in range(3):
        guard.check("t")
    assert guard.history == [0.4, 0.4, 0.4]


def test_drift_relative_percentile_loosens_threshold() -> None:
    """相对口径只能**放宽松**（阈值取更小者），保证不会引入新的误报。"""
    guard = DriftGuard(scorer=ramp(0.05), drift_warn=0.3, drift_block=0.2, relative_percentile=0.5)
    for _ in range(6):  # 先灌入历史，使分位阈值生效
        guard.check("t")
    verdict, _ = guard.check("t")
    # 历史全是 0.05 → 分位阈值 0.05，低于它才算漂移；本次等于 0.05 → 不判漂移
    assert verdict.ok


# ---- G4 循环 ---- #
def test_loop_signature_is_stable_and_param_order_insensitive() -> None:
    a = signature("search", {"q": "x", "page": 1})
    b = signature("search", {"page": 1, "q": "x"})
    c = signature("search", {"page": 2, "q": "x"})
    assert a == b
    assert a != c


def test_loop_guard_detects_repeat_within_window() -> None:
    guard = LoopGuard(window=5, repeat_threshold=3)
    for _ in range(2):
        guard.record("search", {"q": "same"})
    assert guard.check().ok
    guard.record("search", {"q": "same"})
    first = guard.check()
    assert not first.ok and first.action is GuardAction.REPLAN  # 首次 → 强制 replan
    guard.record("search", {"q": "same"})
    second = guard.check()
    assert not second.ok and second.action is GuardAction.ABORT  # 再次 → 终止
    assert guard.hits == 2


def test_loop_guard_ignores_varied_calls() -> None:
    guard = LoopGuard(window=5, repeat_threshold=3)
    for page in range(1, 6):
        guard.record("search", {"q": "x", "page": page})
        assert guard.check().ok


def test_loop_guard_window_limits_history() -> None:
    guard = LoopGuard(window=3, repeat_threshold=3)
    guard.record("search", {"q": "same"})
    for page in range(1, 3):  # 把窗口挤出
        guard.record("search", {"q": f"other{page}"})
    assert guard.check().ok  # 窗口内只剩 1 个 same
    assert len(guard.calls) == 3


# ---- 停滞 ---- #
def test_progress_guard_degrades_then_aborts_on_stagnation() -> None:
    guard = ProgressGuard(no_progress_steps=2)
    assert guard.update(0).ok  # 第 1 次停滞还不触发
    first = guard.update(0)
    assert not first.ok and first.action is GuardAction.DEGRADE
    second = guard.update(0)
    assert not second.ok and second.action is GuardAction.ABORT


def test_progress_guard_resets_on_new_items() -> None:
    guard = ProgressGuard(no_progress_steps=2)
    guard.update(0)
    assert guard.update(3).ok
    assert guard.streak == 0


# ---- 预算看门狗 ---- #
def test_budget_warns_at_eighty_percent_and_stops_at_hundred() -> None:
    watchdog = BudgetWatchdog(max_tokens=100, warn_ratio=0.8)
    assert watchdog.check().ok
    watchdog.add(tokens=80)
    warn = watchdog.check()
    assert not warn.ok and warn.code == "W_BUDGET_NEAR_LIMIT"
    assert warn.action is GuardAction.CONTINUE  # warn 不阻断
    watchdog.add(tokens=20)
    stop = watchdog.check()
    assert not stop.ok and stop.code == "E_BUDGET_EXCEEDED"
    assert stop.action is GuardAction.ABORT


def test_budget_tracks_multiple_dimensions() -> None:
    watchdog = BudgetWatchdog(max_tokens=1000, max_seconds=10, max_usd=1.0, max_steps=5)
    watchdog.add(tokens=100, seconds=1.5, cost_usd=0.2, steps=1)
    usage = watchdog.usage()
    assert usage["tokens_ratio"] == 0.1
    assert usage["seconds_ratio"] == 0.15
    assert usage["cost_ratio"] == 0.2
    assert usage["steps_ratio"] == 0.2


def test_budget_without_limits_always_passes() -> None:
    watchdog = BudgetWatchdog()
    watchdog.add(tokens=10**9, seconds=10**6, cost_usd=1000.0, steps=999)
    assert watchdog.check().ok


# ---- 恢复包与集合调用 ---- #
def test_recovery_packet_contains_reason_trusted_state_and_constraints() -> None:
    verdict = DriftGuard(scorer=ramp(0.01), drift_warn=0.3, drift_block=0.2).check("t")[0]
    packet = build_recovery_packet(
        verdict=verdict,
        stage="analyze",
        trusted_state={"papers": 24, "strategy": "whitelist"},
        next_constraints=["只用已验证论文"],
        attempt=2,
        history=["search:abc"],
    )
    assert packet["guard"]["code"] == "E_GUARD_DRIFT"
    assert packet["failure"]["stage"] == "analyze"
    assert packet["trusted_state"]["papers"] == 24
    assert packet["next_constraints"] == ["只用已验证论文"]
    assert packet["recent_actions"] == ["search:abc"]


def test_guard_rail_checks_only_requested_items() -> None:
    rail = GuardRail(
        drift=DriftGuard(scorer=ramp(0.5), drift_warn=0.3, drift_block=0.2),
        loop=LoopGuard(window=5, repeat_threshold=3),
        progress=ProgressGuard(no_progress_steps=2),
        budget=BudgetWatchdog(max_tokens=1000),
    )
    only_budget = rail.check_all()
    assert len(only_budget) == 2  # loop + budget
    with_progress = rail.check_all(product_text="t", new_items=0)
    assert len(with_progress) == 4  # drift + loop + progress + budget
