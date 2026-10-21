"""熔断器（S9）：三态 `closed → open → half_open`。

语义
- `closed`：正常放行；连续失败达到 `failure_threshold` → `open`；
- `open`：直接拒绝（调用方应降级），冷却 `cooldown_s` 后进入 `half_open`；
- `half_open`：放行**一次**试探；成功 → `closed`（清零），失败 → `open`（重新计时）。

时间由注入的 `clock` 提供（默认 `time.monotonic`），保证测试确定性。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

__all__ = ["BreakerState", "CircuitBreaker"]

BreakerState = str  # "closed" | "open" | "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_s: float = 60.0
    clock: Callable[[], float] = time.monotonic
    state: BreakerState = "closed"
    failures: int = 0
    opened_at: float = 0.0
    _half_open_trial: bool = field(default=False, repr=False)

    def allow(self) -> bool:
        """是否允许本次调用。"""
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.clock() - self.opened_at >= self.cooldown_s:
                self.state = "half_open"
                self._half_open_trial = False
            else:
                return False
        if self.state == "half_open":
            if self._half_open_trial:
                return False
            self._half_open_trial = True
            return True
        return False

    def record_success(self) -> None:
        self.state = "closed"
        self.failures = 0
        self._half_open_trial = False

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = self.clock()
            self._half_open_trial = False

    def snapshot(self) -> dict[str, object]:
        return {"state": self.state, "failures": self.failures}
