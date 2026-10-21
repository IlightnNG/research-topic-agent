"""上下文槽位（S7）：分区管理 + **物化进事件**。

为什么物化：若注入内容只拼进 prompt 而不落库，同一 run 回放时 prompt 可能不同，
F8（缓存即复现）与"可审计"都会失效。`materialize_slots()` 把每个非空槽写一条
`phase_change`（stage=context, phase=context, slot, sha）——正文不在事件里，只存摘要与哈希。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from lit_agent.errors import E_CONFIG_INVALID, LitError

__all__ = ["CtxSlot", "SlotRegistry", "VALID_SLOTS", "materialize_slots"]

VALID_SLOTS = ("system", "scope", "evidence", "recovery", "memory")


@dataclass(frozen=True)
class CtxSlot:
    name: str
    content: str = ""
    source: str = ""
    priority: int = 0


@dataclass
class SlotRegistry:
    slots: dict[str, CtxSlot] = field(default_factory=dict)

    def register(self, slot: CtxSlot) -> None:
        if slot.name not in VALID_SLOTS:
            raise LitError(
                E_CONFIG_INVALID,
                f"未知槽位 {slot.name!r}（合法：{VALID_SLOTS}）",
                context={"slot": slot.name},
            )
        if slot.name in self.slots:
            raise LitError(
                E_CONFIG_INVALID, f"槽位重复注册：{slot.name}", context={"slot": slot.name}
            )
        self.slots[slot.name] = slot

    def get(self, name: str) -> CtxSlot | None:
        return self.slots.get(name)

    def render(self) -> str:
        """按优先级降序拼接（确定性：优先级相同按名字）。"""
        ordered = sorted(self.slots.values(), key=lambda item: (-item.priority, item.name))
        return "\n\n".join(slot.content for slot in ordered if slot.content)


def materialize_slots(registry: SlotRegistry, log: Any, *, stage: str = "context") -> int:
    """把非空槽写进事件（幂等：同 slot 同 sha 只写一次）。返回写入条数。"""
    from lit_agent.models.event import EventType

    written = 0
    for slot in sorted(registry.slots.values(), key=lambda item: item.name):
        if not slot.content:
            continue
        digest = hashlib.sha256(slot.content.encode("utf-8")).hexdigest()[:12]
        key = f"context:{slot.name}:{digest}"
        if hasattr(log, "has_dedupe") and log.has_dedupe(key):
            continue
        log.emit(
            EventType.PHASE_CHANGE,
            stage=stage,
            payload={
                "phase": "context",
                "slot": slot.name,
                "sha": digest,
                "chars": len(slot.content),
                "source": slot.source,
            },
            dedupe_key=key,
        )
        written += 1
    return written
