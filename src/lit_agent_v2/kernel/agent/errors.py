"""Kernel error taxonomy and structured error object."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "KERNEL_ERROR_CODES",
    "KernelError",
]

KERNEL_ERROR_CODES = (
    "E_KERNEL_INVALID_ACTION",
    "E_KERNEL_MAX_STEPS",
    "E_KERNEL_TIMEOUT",
    "E_KERNEL_CANCELLED",
    "E_KERNEL_REPAIR_EXHAUSTED",
    "E_KERNEL_OUTPUT_SCHEMA",
    "E_KERNEL_CHECKPOINT",
    "E_KERNEL_BUDGET",
    "E_KERNEL_TOOL_BUDGET",
    "E_MODEL_FAILED",
    "E_MODEL_TIMEOUT",
    "E_MODEL_RATE_LIMIT",
    "E_TOOL_NOT_FOUND",
    "E_TOOL_NOT_ALLOWED",
    "E_TOOL_SCHEMA",
    "E_TOOL_TIMEOUT",
    "E_TOOL_OUTPUT_SCHEMA",
    "E_TOOL_POLICY_DENIED",
)


@dataclass(frozen=True)
class KernelError:
    code: str
    message: str
    retryable: bool = False
    details: dict[str, object] = field(default_factory=dict)
