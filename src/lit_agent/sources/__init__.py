"""源适配层（guide §3）：OpenAlex 主 + arXiv 辅 + 白名单按 `source.id`。

模块职责：
- `base`     协议、`SyncResult`、HTTP 错误分类与退避重试
- `normalize` 归一化、canonical id、OpenAlex work → `Paper`（自 Phase 0 迁移）
- `whitelist` 名称 → `source.id` 解析与白名单判定
- `openalex`  游标深分页 + 增量水位线 + 日期过滤
- `arxiv`     category 抓取
- `sync`      一次同步的编排（落 `papers` / `papers_raw` / `sync_state`）
"""

from __future__ import annotations

from lit_agent.sources.base import SourceAdapter, SyncResult
from lit_agent.sources.openalex import OpenAlexAdapter

__all__ = ["OpenAlexAdapter", "SourceAdapter", "SyncResult"]
