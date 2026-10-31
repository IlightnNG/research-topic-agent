"""M2-P01: metadata completeness and fulltext fallback."""

from __future__ import annotations

from pathlib import Path

from lit_agent_v2.contracts.report import Paper
from lit_agent_v2.domains.report.ingest import IngestService
from lit_agent_v2.domains.report.pdf import download_html_text
from lit_agent_v2.domains.report.source import SourceService
from lit_agent_v2.metrics.store import MetricStore
from lit_agent_v2.storage.db import Database


def _paper(index: int, *, title: str | None = None) -> Paper:
    return Paper(
        paper_id=f"P{index}",
        title=title if title is not None else f"Tool use study {index}",
        abstract=f"Tool use improves task success in study {index}.",
        authors=[f"Author {index}"],
        venue="ACL",
        year=2025,
    )


def test_metadata_metrics_and_empty_title_filter(tmp_path: Path) -> None:
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    metrics = MetricStore(db)
    service = SourceService(metrics)
    artifact = service.select(
        topic_id="t",
        query="tool use",
        papers=[_paper(index) for index in range(9)] + [_paper(9, title="")],
        limit=10,
        run_id="r1",
    )
    assert len(artifact.papers) == 9
    points = {point["metric_id"]: point["value"] for point in metrics.points("r1")}
    assert points["metadata.completeness"] == 1.0
    assert points["metadata.authors_rate"] == 1.0


def test_html_fallback_and_ingest_fulltext(
    tmp_path: Path, monkeypatch
) -> None:
    class Adapter:
        def fetch(self, query, **kwargs):  # noqa: ANN001
            return [
                Paper(
                    paper_id="P1",
                    title="Tool use",
                    abstract="Tool use improves task success.",
                    html_url="https://example.org/p1",
                    authors=["Ada Lovelace"],
                    venue="ACL",
                    year=2025,
                )
            ]

    monkeypatch.setattr(
        "lit_agent_v2.domains.report.pdf.download_pdf_text",
        lambda url, **kwargs: "",
    )
    monkeypatch.setattr(
        "lit_agent_v2.domains.report.pdf.download_html_text",
        lambda url, **kwargs: "Full text of the paper.",
    )
    corpus = IngestService(Adapter(), tmp_path / "corpus").ingest(
        "tool use", limit=1, fulltext_limit=1
    )
    papers = corpus.papers()
    assert papers[0].fulltext == "Full text of the paper."
    assert papers[0].authors == ["Ada Lovelace"]


def test_download_html_text_strips_markup() -> None:
    import httpx

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, text="<html><script>x()</script><body>Tool use improves success.</body></html>"
        )
    )
    with httpx.Client(transport=transport) as client:
        text = download_html_text("https://example.org", client=client)
    assert "Tool use improves success." in text
    assert "<body>" not in text
