"""OpenAlex 适配器（主源）：礼貌池 + 游标深分页 + 增量水位线 + 日期合理性过滤。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from lit_agent.config import Settings
from lit_agent.errors import E_SRC_NO_SELECTOR, LitError
from lit_agent.models.paper import Paper
from lit_agent.sources.base import Backoff, request_json
from lit_agent.sources.normalize import openalex_work_to_paper

__all__ = [
    "WORK_ENDPOINT",
    "OpenAlexAdapter",
    "build_filter",
    "date_is_sane",
    "fetch_works_page",
]

WORK_ENDPOINT = "https://api.openalex.org/works"
_OPENALEX_ID = "https://openalex.org/"


def _venue_filter(venue_ids: list[str]) -> str:
    clean = [venue_id.replace(_OPENALEX_ID, "") for venue_id in venue_ids if venue_id]
    if not clean:
        raise LitError(
            E_SRC_NO_SELECTOR,
            "selector.venue_ids 为空：白名单尚未解析（Step 1.6 的 resolve_venues）"
            "或配置有误；禁止退化为全量抓取",
            context={"venue_ids": list(venue_ids)},
        )
    return "primary_location.source.id:" + "|".join(clean)


def build_filter(selector: dict[str, Any], *, since: str | None) -> str:
    """拼 OpenAlex `filter` 参数（白名单 + 起始日期 + 类型）。"""
    parts = [_venue_filter(list(selector.get("venue_ids") or []))]
    from_year = selector.get("from_year")
    start = since or (f"{int(from_year)}-01-01" if from_year else None)
    if start:
        parts.append(f"from_publication_date:{start}")
    work_type = selector.get("type")
    if work_type:
        parts.append(f"type:{work_type}")
    return ",".join(parts)


def date_is_sane(work: dict[str, Any], *, today: date | None = None) -> bool:
    """日期合理性：拒绝未来日期 / 明显非法年份（源侧偶有占位值）。"""
    reference = today or datetime.now(UTC).date()
    raw = (
        work.get("publication_date")
        or work.get("first_publication_date")
        or work.get("updated_date")
    )
    if not raw:
        return True  # 缺日期不丢（后续 year 过滤在业务侧做）
    try:
        parsed = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return False
    if parsed > reference + timedelta(days=1):
        return False
    return parsed.year >= 1800


def fetch_works_page(
    client: httpx.Client,
    *,
    selector: dict[str, Any],
    since: str | None,
    cursor: str = "*",
    per_page: int = 200,
    mailto: str = "",
    api_key: str = "",
    backoff: Backoff | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """取一页 works，返回 (results, next_cursor)。"""
    params: dict[str, Any] = {
        "filter": build_filter(selector, since=since),
        "per-page": per_page,
        "cursor": cursor,
    }
    if mailto:
        params["mailto"] = mailto  # polite pool
    if api_key:
        params["api_key"] = api_key  # 有 key 才有稳定的日配额（否则共享池会 401）
    payload = request_json(client, WORK_ENDPOINT, params=params, backoff=backoff)
    results = payload.get("results")
    if results is None or not isinstance(results, list):
        from lit_agent.errors import E_SRC_SCHEMA

        raise LitError(
            E_SRC_SCHEMA, "OpenAlex 响应缺少 results 列表", context={"keys": sorted(payload)}
        )
    meta = payload.get("meta") or {}
    next_cursor = meta.get("next_cursor")
    return results, (str(next_cursor) if next_cursor else None)


class OpenAlexAdapter:
    """`SourceAdapter` 实现：逐页产出 `Paper`（原始 JSON 另行提供，供 `papers_raw`）。"""

    name = "openalex"

    def __init__(
        self,
        *,
        per_page: int = 200,
        mailto: str = "",
        api_key: str = "",
        backoff: Backoff | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.per_page = per_page
        self.mailto = mailto
        self.api_key = api_key
        self.backoff = backoff or Backoff()
        self._client = client

    @classmethod
    def from_settings(
        cls, settings: Settings, *, client: httpx.Client | None = None
    ) -> OpenAlexAdapter:
        source = settings.sources.openalex
        return cls(
            per_page=source.per_page,
            mailto=source.mailto,
            api_key=source.api_key.get_secret_value() if source.api_key else "",
            backoff=Backoff(max_retries=source.max_retries),
            client=client,
        )

    def _client_or_new(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=30.0), True

    def fetch_works(
        self, *, since: str | None, selector: dict[str, Any], limit: int | None = None
    ) -> Iterator[dict[str, Any]]:
        """逐条产出原始 work（供 `papers_raw` 原样留存）。"""
        client, owned = self._client_or_new()
        emitted = 0
        cursor: str | None = "*"
        try:
            while cursor:
                works, cursor = fetch_works_page(
                    client,
                    selector=selector,
                    since=since,
                    cursor=cursor,
                    per_page=self.per_page,
                    mailto=self.mailto,
                    api_key=self.api_key,
                    backoff=self.backoff,
                )
                if not works:
                    break
                for work in works:
                    if not date_is_sane(work):
                        continue
                    yield work
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return
        finally:
            if owned:
                client.close()

    def fetch(
        self, *, since: str | None = None, selector: dict[str, Any], limit: int | None = None
    ) -> Iterator[Paper]:
        for work in self.fetch_works(since=since, selector=selector, limit=limit):
            yield openalex_work_to_paper(work)

    def health(self) -> dict[str, Any]:
        return {
            "source": self.name,
            "endpoint": WORK_ENDPOINT,
            "mailto_configured": bool(self.mailto),
        }
