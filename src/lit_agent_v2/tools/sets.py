"""Named tool sets. General and domain tools share one runtime."""

from __future__ import annotations

GENERAL_TOOLSET = (
    "context.inspect",
    "context.compact",
    "plan.create",
    "plan.update",
    "plan.read",
    "plan.complete_step",
    "memory.write",
    "memory.search",
    "artifact.put",
    "artifact.get",
    "fs.read",
    "fs.list",
    "fs.write",
    "test.run",
    "verify.code",
    "verify.audit",
)

REPORT_TOOLSET = GENERAL_TOOLSET + (
    "report.plan",
    "report.write_section",
    "report.check_section",
    "report.assemble",
    "report.persist",
)

SOURCE_TOOLSET = GENERAL_TOOLSET + (
    "source.search",
    "source.fetch_pdf",
    "source.fetch_html",
    "fulltext.extract",
    "corpus.store",
    "corpus.dedupe",
)

EVIDENCE_TOOLSET = GENERAL_TOOLSET + (
    "corpus.read",
    "claims.extract",
    "quote.check",
    "claims.dedupe",
    "evidence.stats",
)

CHAT_TOOLSET = GENERAL_TOOLSET + (
    "corpus.papers",
    "chat.answer",
)

__all__ = [
    "CHAT_TOOLSET",
    "EVIDENCE_TOOLSET",
    "GENERAL_TOOLSET",
    "REPORT_TOOLSET",
    "SOURCE_TOOLSET",
]
