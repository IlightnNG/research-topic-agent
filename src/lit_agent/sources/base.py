"""源适配层公共契约（guide §3）。

- `SourceAdapter` 协议：`fetch(since, selector) -> Iterator[Paper]`；
- HTTP 失败统一映射到 `E_SRC_*`（4xx / 429 / 5xx / timeout / schema）；
- 重试策略集中在这里，适配器不各写一套退避。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from lit_agent.errors import (
    E_SRC_4XX,
    E_SRC_5XX,
    E_SRC_AUTH,
    E_SRC_RATE,
    E_SRC_SCHEMA,
    E_SRC_TIMEOUT,
    LitError,
)
from lit_agent.models.paper import Paper

__all__ = [
    "Backoff",
    "SourceAdapter",
    "SyncResult",
    "classify_status",
    "request_json",
]


class SourceAdapter(Protocol):
    name: str

    def fetch(
        self,
        *,
        since: str | None = None,
        selector: dict[str, Any],
        limit: int | None = None,
    ) -> Iterator[Paper]: ...

    def health(self) -> dict[str, Any]: ...


@dataclass
class SyncResult:
    """一次同步的计数（用于断言"第二次 new=0"）。"""

    source: str
    fetched: int = 0
    papers_new: int = 0
    papers_updated: int = 0
    dropped: int = 0
    cursor: str | None = None
    since: str | None = None
    selector_key: str = ""
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "fetched": self.fetched,
            "papers_new": self.papers_new,
            "papers_updated": self.papers_updated,
            "dropped": self.dropped,
            "cursor": self.cursor,
            "since": self.since,
            "selector_key": self.selector_key,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class Backoff:
    """指数退避参数（秒）。"""

    base: float = 0.5
    factor: float = 2.0
    max_delay: float = 8.0
    max_retries: int = 3

    def delay(self, attempt: int) -> float:
        return min(self.max_delay, self.base * (self.factor ** max(0, attempt - 1)))


def classify_status(status_code: int) -> str:
    """HTTP 状态 → 错误码（429 单独处理，因为它是"可重试的限流"）。"""
    if status_code == 429:
        return E_SRC_RATE
    # 401/403：没有 key、key 无效，或（OpenAlex 免费池）**当日配额已耗尽**——
    # 重试没有意义，必须让人去配 key / 等配额重置，所以单独给一个可指导操作的错误码。
    if status_code in (401, 403):
        return E_SRC_AUTH
    if status_code in (408, 504):
        return E_SRC_TIMEOUT
    if 400 <= status_code < 500:
        return E_SRC_4XX
    if 500 <= status_code < 600:
        return E_SRC_5XX
    return E_SRC_SCHEMA


def request_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    backoff: Backoff | None = None,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """带退避重试的 JSON GET。失败抛 `LitError(E_SRC_*)`。"""
    policy = backoff or Backoff()
    last_error: LitError | None = None
    for attempt in range(1, policy.max_retries + 2):
        try:
            response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            last_error = LitError(E_SRC_TIMEOUT, f"请求超时：{url}（{exc}）", context={"url": url})
        except httpx.HTTPError as exc:
            last_error = LitError(E_SRC_SCHEMA, f"请求失败：{url}（{exc}）", context={"url": url})
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError:
                    raise LitError(
                        E_SRC_SCHEMA, f"响应不是合法 JSON：{url}", context={"url": url}
                    ) from None
            code = classify_status(response.status_code)
            last_error = LitError(
                code,
                f"源接口返回 {response.status_code}：{url}",
                context={"url": url, "status": response.status_code},
            )
            if code not in (E_SRC_RATE, E_SRC_5XX, E_SRC_TIMEOUT):
                raise last_error
        if attempt > policy.max_retries:
            break
        sleep(policy.delay(attempt))
    raise last_error or LitError(E_SRC_SCHEMA, f"未知失败：{url}")
