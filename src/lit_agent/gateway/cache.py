"""内容寻址缓存键（可复现性来源，F8）：键必须覆盖一切影响输出的参数。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = ["request_sha"]


def request_sha(
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    schema_version: str = "1.0",
) -> str:
    """`sha256(model + messages + temperature + max_tokens + schema_version)`。"""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "schema_version": schema_version,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
