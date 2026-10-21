"""LLM 网关（guide §5）：单一出口 = 敏感硬门 → 缓存 → 预算 → 调用 → 截断重试 → 计量。

关键纪律
- **先判敏感再出网**：`strict` 命中直接抛 `E_POLICY_SENSITIVE`，调用计数必须为 0；
- **缓存命中 cost=0**，且输出与首次逐字节一致（可复现性）；
- **截断检测**：`finish_reason == "length"` 或正文为空 → 判失败，`max_tokens` 翻倍重试一次；
  仍失败 → `E_LLM_TRUNCATED`（Phase 0 静默错误 #10：空正文不能当成功）；
- **预算在调用前判**；调用后写 `llm_calls`（usage 缺失时估算并标 `cost_estimated`）。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lit_agent.config import Settings
from lit_agent.db.repo import llm_calls as llm_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import (
    E_BUDGET_COST,
    E_LLM_5XX,
    E_LLM_QUOTA,
    E_LLM_TRUNCATED,
    E_SCHEMA_STAGE_OUTPUT,
    LitError,
)
from lit_agent.gateway import cache as cache_mod
from lit_agent.gateway import policy
from lit_agent.gateway.breaker import CircuitBreaker
from lit_agent.gateway.metering import BudgetGuard, CallUsage, estimate_tokens

__all__ = ["LLMCall", "LLMGateway"]

Completer = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class LLMCall:
    ok: bool
    content: str
    model: str
    cached: bool = False
    attempts: int = 1
    usage: CallUsage = field(default_factory=CallUsage)
    route_reason: str = ""
    error_code: str | None = None


def _parse_response(response: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "")
    finish = str(choice.get("finish_reason") or "")
    usage = response.get("usage") or {}
    return content, finish, usage if isinstance(usage, dict) else {}


class LLMGateway:
    """进程内单例即可；`engine` 可注入（测试用临时库）。"""

    def __init__(
        self,
        settings: Settings,
        *,
        completer: Completer | None = None,
        budget: BudgetGuard | None = None,
        breaker: CircuitBreaker | None = None,
        engine: Any | None = None,
    ) -> None:
        self.settings = settings
        self.model = settings.providers.cloud.model
        self._completer = completer
        self.budget = budget or BudgetGuard(settings.routing.run_cost_budget_usd)
        self.breaker = breaker or CircuitBreaker()
        self._engine = engine
        self.calls = 0  # 真实出网次数（测试断言敏感样本为 0）

    # ------------------------------------------------------------------ #
    # 基础设施
    # ------------------------------------------------------------------ #
    def _get_engine(self) -> Any:
        if self._engine is None:
            self._engine = make_engine(self.settings)
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def _complete(
        self, messages: list[dict[str, Any]], *, temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        if self._completer is not None:
            self.calls += 1
            return self._completer(
                messages=messages,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        import litellm

        cloud = self.settings.providers.cloud
        key = cloud.api_key.get_secret_value() if cloud.api_key is not None else None
        self.calls += 1
        return litellm.completion(
            model=f"{cloud.name}/{self.model}" if "/" not in self.model else self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=key,
            base_url=cloud.base_url,
            timeout=cloud.timeout_s,
        )

    def _usage(
        self, usage: dict[str, Any], messages: list[dict[str, Any]], content: str
    ) -> CallUsage:
        req = usage.get("prompt_tokens")
        resp = usage.get("completion_tokens")
        cost = usage.get("cost") or usage.get("response_cost")
        estimated = False
        if req is None:
            req = estimate_tokens(policy.messages_to_text(messages))
            estimated = True
        if resp is None:
            resp = estimate_tokens(content)
            estimated = True
        if cost is None:
            cost = 0.0
            estimated = True
        return CallUsage(
            req_tokens=int(req), resp_tokens=int(resp), cost=float(cost), estimated=estimated
        )

    # ------------------------------------------------------------------ #
    # 公开 API
    # ------------------------------------------------------------------ #
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        run_id: str | None = None,
        agent: str | None = None,
    ) -> LLMCall:
        cloud = self.settings.providers.cloud
        limit = int(max_tokens or cloud.max_tokens)
        decision = policy.decide(messages, sensitivity=self.settings.routing.sensitivity)

        sha = cache_mod.request_sha(self.model, messages, temperature=temperature, max_tokens=limit)
        engine = self._get_engine()
        with connect(engine) as conn:
            row = llm_repo.cache_get(conn, sha)
            if row is not None:
                llm_repo.cache_hit(conn, sha)
                cached_payload = json.loads(row._mapping["response_json"])
                content = str(cached_payload.get("content") or "")
                usage = CallUsage(cost=0.0, estimated=False)
                llm_repo.record(
                    conn,
                    run_id=run_id,
                    agent=agent,
                    provider=cloud.name,
                    model=self.model,
                    route_reason=decision.reason,
                    request_sha=sha,
                    cache_hit=True,
                    req_tokens=usage.req_tokens,
                    resp_tokens=usage.resp_tokens,
                    cost=0.0,
                )
                return LLMCall(
                    ok=True,
                    content=content,
                    model=self.model,
                    cached=True,
                    attempts=0,
                    usage=usage,
                    route_reason=decision.reason,
                )

        if not self.breaker.allow():
            raise LitError(
                E_LLM_QUOTA,
                f"熔断器打开，拒绝调用（{self.breaker.snapshot()}）",
                context=self.breaker.snapshot(),
            )

        state = self.budget.check()
        if state == "stop":
            raise LitError(
                E_BUDGET_COST,
                f"预算已用尽（{self.budget.snapshot()}），拒绝再次调用",
                context=self.budget.snapshot(),
            )

        attempts = 0
        tokens = limit
        while True:
            attempts += 1
            try:
                response = self._complete(messages, temperature=temperature, max_tokens=tokens)
            except LitError:
                self.breaker.record_failure()
                raise
            except Exception as exc:  # noqa: BLE001 - provider 异常统一映射
                self.breaker.record_failure()
                raise LitError(
                    E_LLM_5XX, f"LLM 调用失败：{type(exc).__name__}: {str(exc)[:160]}"
                ) from None

            content, finish, raw_usage = _parse_response(response)
            truncated = finish == "length" or not content.strip()
            if truncated and attempts == 1:
                tokens *= 2  # 截断 → 放大预算重试一次
                continue
            if truncated:
                usage = self._usage(raw_usage, messages, content)
                with connect(engine) as conn:
                    llm_repo.record(
                        conn,
                        run_id=run_id,
                        agent=agent,
                        provider=cloud.name,
                        model=self.model,
                        route_reason=decision.reason,
                        request_sha=sha,
                        req_tokens=usage.req_tokens,
                        resp_tokens=usage.resp_tokens,
                        cost=usage.cost,
                        cost_estimated=usage.estimated,
                        degraded=True,
                        ok=False,
                        error_code=E_LLM_TRUNCATED,
                    )
                raise LitError(
                    E_LLM_TRUNCATED,
                    f"重试后仍被截断（finish_reason={finish!r}, max_tokens={tokens}）",
                    context={"finish_reason": finish, "max_tokens": tokens},
                )
            break

        usage = self._usage(raw_usage, messages, content)
        with connect(engine) as conn:
            llm_repo.record(
                conn,
                run_id=run_id,
                agent=agent,
                provider=cloud.name,
                model=self.model,
                route_reason=decision.reason,
                request_sha=sha,
                req_tokens=usage.req_tokens,
                resp_tokens=usage.resp_tokens,
                cost=usage.cost,
                cost_estimated=usage.estimated,
            )
            llm_repo.cache_put(
                conn,
                sha,
                model=self.model,
                response_json=json.dumps({"content": content}, ensure_ascii=False),
                usage_json=json.dumps(raw_usage, ensure_ascii=False, default=str),
            )
        self.breaker.record_success()
        self.budget.spend(usage)
        return LLMCall(
            ok=True,
            content=content,
            model=self.model,
            cached=False,
            attempts=attempts,
            usage=usage,
            route_reason=decision.reason,
        )

    def chat_json(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> tuple[dict[str, Any], LLMCall]:
        call = self.chat(messages, **kwargs)
        text = call.content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            return json.loads(text), call
        except ValueError as exc:
            raise LitError(
                E_SCHEMA_STAGE_OUTPUT,
                f"LLM 输出不是合法 JSON：{exc}",
                context={"preview": text[:200]},
            ) from None
