"""CLI 入口：`python -m lit_agent_min [selfcheck] [--lax] [--config PATH]`。

约定：后续 Step 的子命令（如 s1_coverage）也挂在这里，保持单一入口、易扩展。
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, selfcheck


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lit_agent_min",
        description="Phase 0 最小内核：自检与工具入口",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("selfcheck", help="检查配置、目录与密钥环境（默认命令）")
    check.add_argument("--lax", action="store_true", help="缺少密钥只告警，不返回失败码")
    check.add_argument("--config", default=None, help="指定配置文件路径")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "selfcheck"):
        return selfcheck(
            strict=not getattr(args, "lax", False),
            config_path=getattr(args, "config", None),
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:  # pragma: no cover - 交互中断
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None
