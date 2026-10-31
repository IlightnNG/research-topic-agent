"""Shared error contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ModuleError"]


@dataclass
class ModuleError(Exception):
    code: str
    message: str
    module: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
