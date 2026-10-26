"""3.4 / S19：最小沙盒策略（不执行命令，只做准入判断）。

真实执行留给 P4 的 `code-runtime`；当前先保证"越权命令/越界路径"在 API 层被拒。
"""

from __future__ import annotations

import re
from pathlib import Path

from lit_agent.errors import E_PERMISSION_REQUIRED, LitError

__all__ = ["DEFAULT_ALLOWLIST", "check_command", "ensure_within"]

DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {"python", "python3", "pytest", "ruff", "node", "npm", "uv"}
)

_SHELL_META = re.compile(r"[;&|`$><]")


def check_command(
    argv: list[str] | tuple[str, ...],
    *,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
    allow_network: bool = False,
) -> None:
    """拒绝未授权可执行文件、shell 元字符与网络命令（默认无网）。"""
    if not argv:
        raise LitError(E_PERMISSION_REQUIRED, "空命令", context={"stage": "sandbox"})
    exe = Path(str(argv[0])).name.lower()
    allowed = set(allowlist)
    if allow_network:
        allowed |= {"curl", "wget"}
    if exe not in allowed:
        raise LitError(
            E_PERMISSION_REQUIRED,
            f"命令不在白名单：{exe}",
            context={"stage": "sandbox", "argv": list(argv)[:3]},
        )
    for token in argv:
        if _SHELL_META.search(str(token)):
            raise LitError(
                E_PERMISSION_REQUIRED,
                "命令包含 shell 元字符",
                context={"stage": "sandbox", "token": str(token)[:80]},
            )


def ensure_within(root: Path, target: Path) -> Path:
    """把 target 解析为绝对路径，越出 root 即拒绝（防目录穿越）。"""
    root_resolved = root.resolve()
    target_resolved = (root_resolved / target).resolve() if not target.is_absolute() else target.resolve()
    try:
        target_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise LitError(
            E_PERMISSION_REQUIRED,
            f"路径越界：{target}",
            context={"stage": "sandbox", "root": str(root_resolved)},
        ) from exc
    return target_resolved
