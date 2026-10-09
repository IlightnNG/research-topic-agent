"""云 LLM 网关（Phase 0 step 5.6 的依赖；对应选型文档的 LiteLLM 网关档）。

职责边界
- 只负责"把一次 LLM 调用变成可审计的事实"：**调用、重试、截断检测、计量、缓存、埋点**。
- 不构造业务提示词、不解析业务语义（那是 `agents/` 与 steps 的事）。
- 不打印/记录任何请求或响应正文（日志规范：正文守卫 + 脱敏）。

实测约束（2026-10-08，`deepseek/deepseek-flash`，见 `prototype/RESULTS.md` §2.12）
1. **它是 reasoning 模型**：先产出 `reasoning_content`，该部分**同样计入 completion_tokens**。
   若 `max_tokens` 给小了，会出现 `content=''` 且 `finish_reason='length'` —— **静默返回空内容**。
   因此本网关把 `finish_reason == "length"` 一律判为**截断失败**并放大预算重试，绝不把空串当成功。
2. 延迟：最小调用 1.2–3.3 s，真实抽取任务 ~2.1 s；但**首包可能异常慢**（实测一次 186 s），
   所以超时要给足（默认 120 s）并按指数退避重试。
3. `litellm.completion_cost()` 对该模型可用（约 $0.0004/1k tokens）；查不到价格时记 `cost_known=False`
   而不是编造数字。
4. `response_format={"type": "json_object"}` 可用且稳定 → 结构化抽取走 JSON 模式。

设计要点
- **内容寻址缓存**：key = sha1(model|messages|params)，命中则不发请求（重跑不花钱、结果可复现）。
  缓存是"重跑成本可重复"这条验收标准的实现手段，也是导师演示时不必依赖网络的保险。
- **预算熔断**：累计成本超过 `budget_usd` 立即停止后续调用并抛 `LLMBudgetExceeded`
  （S6 的预算看门狗在此之上做编排层降级）。
- **可注入 completer**：单测传入假函数即可离线验证缓存/截断/重试逻辑，测试不触网。
- **可审计**：每次调用产出一条 `llm_call` 事件（tokens/cost/latency/cached/attempts），
  与 `logs/app.jsonl` 的日志行通过 `run_id` 关联。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .models import EventType

__all__ = [
    "LLMBudgetExceeded",
    "LLMCall",
    "LLMError",
    "LLMGateway",
    "LLMTruncated",
    "Usage",
]


class LLMError(RuntimeError):
    """可预期的 LLM 调用失败（含 provider 报错与网络异常）。"""


class LLMTruncated(LLMError):
    """输出被 max_tokens 截断（reasoning 模型尤易发生）——必须重试而不是当成功。"""


class LLMBudgetExceeded(LLMError):
    """累计成本超出预算，后续调用一律拒绝。"""


class Completer(Protocol):
    """与 `litellm.completion` 兼容的最小签名（便于注入假实现做离线单测）。"""

    def __call__(self, **kwargs: Any) -> Any: ...


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMCall:
    """一次逻辑调用的完整事实（缓存命中时也返回，`cached=True`）。"""

    text: str
    data: dict[str, Any] | None
    model: str
    usage: Usage
    cost_usd: float | None
    cost_known: bool
    latency_ms: float
    attempts: int
    cached: bool
    finish_reason: str | None = None
    reasoning_chars: int = 0
    task: str | None = None
    cache_key: str = ""

    def to_payload(self) -> dict[str, Any]:
        """事件 payload（**不含任何正文**，只留结构化计数）。"""
        return {
            "task": self.task,
            "model": self.model,
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "reasoning_chars": self.reasoning_chars,
            "cost_usd": self.cost_usd,
            "cost_known": self.cost_known,
            "latency_ms": round(self.latency_ms, 1),
            "attempts": self.attempts,
            "cached": self.cached,
            "finish_reason": self.finish_reason,
            "cache_key": self.cache_key,
        }


@dataclass
class _Totals:
    calls: int = 0
    network_calls: int = 0
    cache_hits: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    cost_unknown_calls: int = 0
    latency_ms: float = 0.0
    avoided_tokens: int = 0
    avoided_cost_usd: float = 0.0
    by_task: dict[str, int] = field(default_factory=dict)


class LLMGateway:
    """云 LLM 网关：缓存 + 重试 + 截断检测 + 计量 + 预算熔断 + 事件。"""

    def __init__(
        self,
        *,
        model: str,
        cache_dir: str | Path,
        api_key_env: str = "DEEPSEEK_API_KEY",
        api_base: str | None = None,
        budget_usd: float | None = None,
        timeout_s: float = 120.0,
        max_attempts: int = 3,
        use_cache: bool = True,
        completer: Completer | None = None,
        on_call: Callable[[LLMCall], None] | None = None,
    ) -> None:
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.api_key_env = api_key_env
        self.api_base = api_base
        self.budget_usd = budget_usd
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.use_cache = use_cache
        self.totals = _Totals()
        self._on_call = on_call
        self._completer = completer
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # -- 公开 API ------------------------------------------------------------ #
    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        task: str,
        schema_hint: str | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.0,
    ) -> LLMCall:
        """要求返回 JSON 对象；截断/解析失败会放大预算重试。"""
        return self._call(
            messages,
            task=task,
            json_mode=True,
            schema_hint=schema_hint,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        task: str,
        max_tokens: int = 1200,
        temperature: float = 0.0,
    ) -> LLMCall:
        """纯文本返回（本轮闭环未用，保留给后续 critic/chat 档）。"""
        return self._call(
            messages,
            task=task,
            json_mode=False,
            schema_hint=None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def summary(self) -> dict[str, Any]:
        t = self.totals
        return {
            "calls": t.calls,
            "network_calls": t.network_calls,
            "cache_hits": t.cache_hits,
            "retries": t.retries,
            "prompt_tokens": t.prompt_tokens,
            "completion_tokens": t.completion_tokens,
            "cost_usd": round(t.cost_usd, 6),
            "cost_unknown_calls": t.cost_unknown_calls,
            "avg_latency_ms": round(t.latency_ms / t.network_calls, 1) if t.network_calls else 0.0,
            "cache_hit_rate": round(t.cache_hits / t.calls, 3) if t.calls else 0.0,
            "avoided_tokens_by_cache": t.avoided_tokens,
            "avoided_cost_usd_by_cache": round(t.avoided_cost_usd, 6),
            "by_task": dict(t.by_task),
        }

    # -- 内部 ---------------------------------------------------------------- #
    def _cache_key(self, payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _call(
        self,
        messages: list[dict[str, str]],
        *,
        task: str,
        json_mode: bool,
        schema_hint: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMCall:
        key = self._cache_key(
            {
                "model": self.model,
                "messages": messages,
                "json": json_mode,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "schema_hint": schema_hint,
            }
        )
        self.totals.calls += 1
        self.totals.by_task[task] = self.totals.by_task.get(task, 0) + 1
        self._check_budget(task)

        hit = self._read_cache(key, task)
        if hit is not None:
            return hit

        last_error: Exception | None = None
        budget = max_tokens
        attempts = 0
        started = time.perf_counter()
        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            try:
                response = self._invoke(messages, json_mode, budget, temperature)
                call = self._consume(
                    response,
                    task=task,
                    key=key,
                    attempts=attempts,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
                self._write_cache(key, call)
                self._emit(call)
                return call
            except LLMTruncated as exc:
                last_error = exc
                # reasoning 模型被截断：放大预算重试（每次 ×2）
                budget = min(budget * 2, 8192)
                self.totals.retries += 1
                time.sleep(min(2 ** (attempt - 1) * 0.5, 4.0))
            except Exception as exc:  # noqa: BLE001 - 网络/服务端异常都需重试
                last_error = exc
                self.totals.retries += 1
                if attempt < self.max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 4.0))
        raise LLMError(
            f"LLM 调用失败（task={task}, attempts={attempts}）：{last_error}"
        ) from last_error

    def _invoke(
        self, messages: list[dict[str, str]], json_mode: bool, max_tokens: int, temperature: float
    ) -> Any:
        completer = self._completer or _default_completer()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": self.timeout_s,
            "api_key": _read_env(self.api_key_env),
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        self.totals.network_calls += 1
        return completer(**kwargs)

    def _consume(
        self, response: Any, *, task: str, key: str, attempts: int, latency_ms: float
    ) -> LLMCall:
        choice = response.choices[0]
        message = choice.message
        text = (message.content or "").strip()
        reasoning = getattr(message, "reasoning_content", None) or ""
        finish_reason = getattr(choice, "finish_reason", None)

        usage_raw = getattr(response, "usage", None)
        details = getattr(usage_raw, "completion_tokens_details", None)
        if details is None:
            reasoning_tokens = 0
        elif isinstance(details, dict):
            reasoning_tokens = int(details.get("reasoning_tokens", 0) or 0)
        else:
            reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0)
        usage = Usage(
            prompt_tokens=int(getattr(usage_raw, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage_raw, "completion_tokens", 0) or 0),
            reasoning_tokens=reasoning_tokens,
        )

        cost, cost_known = _cost_of(response)

        # 截断判定（本模型最容易踩的坑）：有 reasoning 却无正文 = 预算被推理吃光
        if finish_reason == "length":
            raise LLMTruncated(
                f"输出被截断（completion_tokens={usage.completion_tokens}, "
                f"reasoning_chars={len(reasoning)}, content_chars={len(text)}）"
            )
        if not text:
            raise LLMTruncated(
                f"空正文（reasoning_chars={len(reasoning)}，finish_reason={finish_reason}）"
            )

        data: dict[str, Any] | None = None
        stripped = _strip_json_fence(text)
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise LLMError(f"JSON 解析失败：{exc}") from None

        self.totals.prompt_tokens += usage.prompt_tokens
        self.totals.completion_tokens += usage.completion_tokens
        self.totals.latency_ms += latency_ms
        if cost_known and cost is not None:
            self.totals.cost_usd += cost
        else:
            self.totals.cost_unknown_calls += 1

        return LLMCall(
            text=text,
            data=data,
            model=str(getattr(response, "model", self.model)),
            usage=usage,
            cost_usd=cost,
            cost_known=cost_known,
            latency_ms=latency_ms,
            attempts=attempts,
            cached=False,
            finish_reason=finish_reason,
            reasoning_chars=len(reasoning),
            task=task,
            cache_key=key,
        )

    def _check_budget(self, task: str) -> None:
        if self.budget_usd is not None and self.totals.cost_usd > self.budget_usd:
            raise LLMBudgetExceeded(
                f"成本已达 ${self.totals.cost_usd:.6f}，超出预算 ${self.budget_usd}（task={task}）"
            )

    def _read_cache(self, key: str, task: str) -> LLMCall | None:
        if not self.use_cache:
            return None
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        self.totals.cache_hits += 1
        usage = Usage(**raw.get("usage", {}))
        call = LLMCall(
            text=raw.get("text", ""),
            data=raw.get("data"),
            model=raw.get("model", self.model),
            usage=usage,
            cost_usd=raw.get("cost_usd"),
            cost_known=bool(raw.get("cost_known")),
            latency_ms=0.0,
            attempts=0,
            cached=True,
            finish_reason=raw.get("finish_reason"),
            reasoning_chars=int(raw.get("reasoning_chars", 0)),
            task=task,
            cache_key=key,
        )
        # 缓存命中**不**计入本次账单（钱在第一次就花了），但记录"本次省下多少"，便于成本对账
        self.totals.avoided_tokens += usage.total
        if call.cost_known and call.cost_usd:
            self.totals.avoided_cost_usd += call.cost_usd
        self._emit(call)
        return call

    def _write_cache(self, key: str, call: LLMCall) -> None:
        if not self.use_cache:
            return
        payload = {
            "model": call.model,
            "text": call.text,
            "data": call.data,
            "usage": {
                "prompt_tokens": call.usage.prompt_tokens,
                "completion_tokens": call.usage.completion_tokens,
                "reasoning_tokens": call.usage.reasoning_tokens,
            },
            "cost_usd": call.cost_usd,
            "cost_known": call.cost_known,
            "finish_reason": call.finish_reason,
            "reasoning_chars": call.reasoning_chars,
        }
        with contextlib.suppress(OSError):  # 缓存写失败不影响主流程（只是下次要重新调用）
            self._cache_path(key).write_text(
                json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    def _emit(self, call: LLMCall) -> None:
        if self._on_call is not None:
            self._on_call(call)


def _read_env(name: str) -> str | None:
    import os

    return os.environ.get(name) or None


def _default_completer() -> Completer:
    import litellm

    litellm.telemetry = False
    litellm.suppress_debug_info = True
    return litellm.completion  # type: ignore[return-value]


def _cost_of(response: Any) -> tuple[float | None, bool]:
    try:
        import litellm

        return float(litellm.completion_cost(response)), True
    except Exception:  # noqa: BLE001 - 价格表可能没有新模型
        return None, False


def _strip_json_fence(text: str) -> str:
    """去掉 ```json 围栏（模型偶尔仍会加）。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
        return body.strip()
    return stripped


def make_event_emitter(sink: Any) -> Callable[[LLMCall], None]:
    """把网关回调接到事件日志（`llm_call` 事件）+ 结构化日志（无正文）。"""

    def emit(call: LLMCall) -> None:
        sink.emit(EventType.LLM_CALL, stage="llm", agent="single", payload=call.to_payload())

    return emit
