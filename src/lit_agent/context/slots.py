"""上下文槽位（guide §8）：把"系统提示 / 检索证据 / 恢复包"等分区管理。

Phase 1 只做注册与读取；**填充策略**（谁写哪个槽、优先级如何抢占）留 P3。
重要约定（DSH 对照 P0-3）：槽内容最终要**物化进事件历史**再组装 prompt，
这样同一 run 回放时 prompt 可复现（否则 F8 缓存即复现失效）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lit_agent.errors import E_CONFIG_INVALID, LitError

__all__ = ["CtxSlot", "SlotRegistry"]

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
