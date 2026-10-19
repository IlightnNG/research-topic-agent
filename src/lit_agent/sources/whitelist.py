"""白名单：**必须**按 OpenAlex `source.id` 判定（Phase 0 结论：按名称匹配会漏）。

`resolve_venues()` 把配置里的名称（NeurIPS / IEEE TCOM …）解析成 `source.id`，
结果应回写到 `config/seeds/topics.yaml`；运行期只读 id，不做名称比较。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

import httpx

from lit_agent.sources.base import request_json

__all__ = ["SOURCES_ENDPOINT", "is_whitelisted", "resolve_venues", "selector_key"]

SOURCES_ENDPOINT = "https://api.openalex.org/sources"
_OPENALEX_ID = "https://openalex.org/"


def selector_key(selector: Mapping[str, Any]) -> str:
    """规范化 selector 的短哈希：同一抓取范围共用一个游标（`sync_state.selector`）。"""
    canonical = json.dumps(selector, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().replace("&", "and").split())


def resolve_venues(
    client: httpx.Client,
    names: Collection[str],
    *,
    mailto: str = "",
    per_name: int = 5,
) -> dict[str, str | None]:
    """名称 → `source.id`；解析不到的返回 `None`（调用方必须显式失败，不许静默丢弃）。"""
    resolved: dict[str, str | None] = {}
    for name in names:
        params: dict[str, Any] = {"search": name, "per-page": per_name}
        if mailto:
            params["mailto"] = mailto
        payload = request_json(client, SOURCES_ENDPOINT, params=params)
        results = payload.get("results") or []
        match: str | None = None
        target = _normalize_name(name)
        for item in results:
            display = _normalize_name(str(item.get("display_name") or ""))
            if display == target or target in display:
                raw_id = str(item.get("id") or "")
                match = raw_id.replace(_OPENALEX_ID, "") if raw_id else None
                break
        resolved[name] = match
    return resolved


def is_whitelisted(work: Mapping[str, Any], venue_ids: Collection[str]) -> bool:
    """论文是否属于白名单（按 `primary_location.source.id`，兼容 `locations`）。"""
    if not venue_ids:
        return False
    allowed = {venue_id.replace(_OPENALEX_ID, "") for venue_id in venue_ids}
    candidates: list[str] = []
    location = work.get("primary_location") or {}
    source = (location or {}).get("source") or {}
    if source.get("id"):
        candidates.append(str(source["id"]))
    for item in work.get("locations") or []:
        src = (item or {}).get("source") or {}
        if src.get("id"):
            candidates.append(str(src["id"]))
    return any(candidate.replace(_OPENALEX_ID, "") in allowed for candidate in candidates)
