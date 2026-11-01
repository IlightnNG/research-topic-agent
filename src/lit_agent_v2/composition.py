"""Composition root. The only place that wires concrete implementations."""

from __future__ import annotations

from lit_agent_v2.domains.chat.answer import ChatService
from lit_agent_v2.research.corpus import LocalCorpus

__all__ = ["build_chat_service"]


def build_chat_service(corpus_root, *, composer=None) -> ChatService:
    return ChatService(LocalCorpus(corpus_root), composer=composer)
