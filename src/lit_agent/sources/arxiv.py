"""arXiv 补充源（guide §3）。

`paper_from_entry()` 是纯函数，便于离线测试；网络部分只在 `fetch()` 里。
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

from lit_agent.models.author import Author
from lit_agent.models.paper import Paper
from lit_agent.sources.normalize import canonical_id, name_norm

__all__ = ["ArxivAdapter", "paper_from_entry"]


def _arxiv_id(entry_id: str) -> str:
    return entry_id.rstrip("/").split("/abs/")[-1]


def paper_from_entry(entry: Any) -> Paper:
    """arxiv `Result` → `Paper`（也接受同名属性的假对象，测试不需要网络）。"""
    arxiv_id = _arxiv_id(str(entry.entry_id))
    authors = [
        Author(
            author_id=f"arxiv-author:{name_norm(author.name)}",
            name=author.name,
            name_norm=name_norm(author.name),
        )
        for author in (entry.authors or [])
    ]
    published: datetime | None = getattr(entry, "published", None)
    return Paper(
        paper_id=canonical_id(arxiv_id=arxiv_id, title=str(entry.title), year=None),
        title=" ".join(str(entry.title).split()),
        abstract=" ".join(str(getattr(entry, "summary", "")).split()),
        authors=authors,
        published_at=published,
        updated_at=getattr(entry, "updated", None),
        source="arxiv",
        source_id=arxiv_id,
        is_oa=True,
        oa_pdf_url=str(getattr(entry, "pdf_url", "") or "") or None,
    )


class ArxivAdapter:
    """按 category 抓取（§2.3 的 arXiv 补充路径）。"""

    name = "arxiv"

    def __init__(self, *, page_size: int = 100) -> None:
        self.page_size = page_size

    def fetch(
        self,
        *,
        since: str | None = None,
        selector: dict[str, Any],
        limit: int | None = None,
    ) -> Iterator[Paper]:
        import arxiv

        categories: Sequence[str] = selector.get("categories") or []
        if not categories:
            from lit_agent.errors import E_SRC_NO_SELECTOR, LitError

            raise LitError(E_SRC_NO_SELECTOR, "arxiv selector.categories 为空")
        query = " OR ".join(f"cat:{category}" for category in categories)
        search = arxiv.Search(
            query=query,
            max_results=limit or self.page_size,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        client = arxiv.Client(
            page_size=min(self.page_size, limit or self.page_size), delay_seconds=3
        )
        count = 0
        for entry in client.results(search):
            if (
                since
                and getattr(entry, "published", None)
                and entry.published.date().isoformat() < since
            ):
                continue
            yield paper_from_entry(entry)
            count += 1
            if limit is not None and count >= limit:
                return

    def health(self) -> dict[str, Any]:
        return {"source": self.name, "endpoint": "http://export.arxiv.org/api/query"}
