"""Step-boundary steering inbox for a Node kernel."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

__all__ = ["InboxMessage", "KernelInbox"]


@dataclass
class InboxMessage:
    text: str
    source: str = "user"
    metadata: dict[str, str] = field(default_factory=dict)


class KernelInbox:
    def __init__(self) -> None:
        self._items: deque[InboxMessage] = deque()

    def push(self, text: str, *, source: str = "user") -> None:
        if text.strip():
            self._items.append(InboxMessage(text=text, source=source))

    def drain(self) -> list[InboxMessage]:
        items = list(self._items)
        self._items.clear()
        return items

    def pending(self) -> int:
        return len(self._items)
