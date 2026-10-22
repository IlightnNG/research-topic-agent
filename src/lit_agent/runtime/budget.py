"""三维预算（tokens / cost / 时间），80% warn、100% stop（guide §13 / design G8）。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["RunBudget", "WARN_RATIO"]

WARN_RATIO = 0.8


@dataclass
class RunBudget:
    """单 run 预算。任一一维到达阈值即返回对应状态（最严重者优先）。"""

    limit_usd: float = 2.0
    limit_tokens: int = 300_000
    limit_seconds: float = 900.0
    used_usd: float = 0.0
    used_tokens: int = 0
    started_at: float = field(default_factory=time.monotonic)

    # ------------------------------------------------------------------ #
    def elapsed_s(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def _ratio(self, used: float, limit: float) -> float:
        return 0.0 if limit <= 0 else used / limit

    def ratios(self) -> dict[str, float]:
        return {
            "cost": self._ratio(self.used_usd, self.limit_usd),
            "tokens": self._ratio(self.used_tokens, self.limit_tokens),
            "time": self._ratio(self.elapsed_s(), self.limit_seconds),
        }

    def check(self) -> str:
        """返回 `ok` / `warn` / `stop`。"""
        ratios = self.ratios()
        if any(value >= 1.0 for value in ratios.values()):
            return "stop"
        if any(value >= WARN_RATIO for value in ratios.values()):
            return "warn"
        return "ok"

    def add(self, *, cost_usd: float = 0.0, tokens: int = 0) -> str:
        self.used_usd += max(0.0, float(cost_usd))
        self.used_tokens += max(0, int(tokens))
        return self.check()

    def spend(self, usage: Any) -> str:
        """与网关 `CallUsage` 兼容：`LLMGateway(budget=RunBudget(...))` 可直接复用同一预算对象。

        这样"run 预算"和"LLM 预算"是**同一个计数器**，不再两套账（DSH 对照 P0-2）。
        """
        cost = float(getattr(usage, "cost", 0.0) or 0.0)
        tokens = int(getattr(usage, "req_tokens", 0) or 0) + int(
            getattr(usage, "resp_tokens", 0) or 0
        )
        return self.add(cost_usd=cost, tokens=tokens)

    @classmethod
    def from_db(cls, settings: Any, run_id: str, *, limit_usd: float | None = None) -> RunBudget:
        """从库里重建已花预算（续跑不会清零）。"""
        from sqlalchemy import text as _text

        from lit_agent.db.session import connect, make_engine

        budget = cls(limit_usd=limit_usd if limit_usd is not None else 2.0)
        engine = make_engine(settings)
        try:
            with connect(engine) as conn:
                row = conn.execute(
                    _text(
                        "SELECT COALESCE(SUM(cost), 0), COALESCE(SUM(COALESCE(req_tokens,0)+COALESCE(resp_tokens,0)), 0)"
                        " FROM llm_calls WHERE run_id = :rid"
                    ),
                    {"rid": run_id},
                ).one()
        finally:
            engine.dispose()
        budget.used_usd = float(row[0] or 0.0)
        budget.used_tokens = int(row[1] or 0)
        return budget

    def snapshot(self) -> dict[str, Any]:
        return {
            "used_usd": round(self.used_usd, 6),
            "used_tokens": self.used_tokens,
            "elapsed_s": round(self.elapsed_s(), 2),
            "ratios": {key: round(value, 3) for key, value in self.ratios().items()},
            "state": self.check(),
        }
