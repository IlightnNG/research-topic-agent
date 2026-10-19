"""论文文件存储：`data/papers/<safe-id>.pdf`。

规则
- 文件名必须 ASCII 安全（DOI 含 `/`，源 id 可能含其它字符）→ 转写 + 短哈希消歧；
- 单文件大小上限（默认 50 MB），超限抛 `E_SRC_SCHEMA`（源侧给了不可用内容）；
- 只存 OA 全文（版权边界，guide §3）。
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from lit_agent.config import Settings
from lit_agent.errors import E_SRC_SCHEMA, LitError

__all__ = ["MAX_PDF_MB", "paper_path", "prune", "safe_stem", "save_pdf"]

MAX_PDF_MB = 50
_SAFE = re.compile(r"[^0-9A-Za-z._-]+")


def safe_stem(paper_id: str) -> str:
    """把任意 paper_id 变成稳定的 ASCII 文件名主干（保留可读性 + 哈希消歧）。"""
    cleaned = _SAFE.sub("_", paper_id).strip("._-") or "paper"
    digest = hashlib.sha1(paper_id.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:100]}_{digest}"


def paper_path(settings: Settings, paper_id: str) -> Path:
    return settings.storage.papers_path / f"{safe_stem(paper_id)}.pdf"


def save_pdf(
    settings: Settings,
    paper_id: str,
    content: bytes,
    *,
    max_mb: int = MAX_PDF_MB,
) -> Path:
    """写入 PDF（幂等覆盖），返回路径。"""
    limit = max_mb * 1024 * 1024
    if len(content) > limit:
        raise LitError(
            E_SRC_SCHEMA,
            f"PDF 超过大小上限（{len(content) / 1048576:.1f} MB > {max_mb} MB）：{paper_id}",
            context={"paper_id": paper_id, "bytes": len(content), "limit": limit},
        )
    if not content.startswith(b"%PDF"):
        raise LitError(
            E_SRC_SCHEMA,
            f"不是 PDF（缺少 %PDF 魔数）：{paper_id}",
            context={"paper_id": paper_id, "head": content[:8].hex()},
        )
    target = paper_path(settings, paper_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def prune(settings: Settings, *, keep_days: int = 30, now: float | None = None) -> int:
    """删除超过 `keep_days` 天未更新的 PDF（返回删除数量）。"""
    root = settings.storage.papers_path
    if not root.exists():
        return 0
    cutoff = (time.time() if now is None else now) - keep_days * 86400
    removed = 0
    for path in root.glob("*.pdf"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed
