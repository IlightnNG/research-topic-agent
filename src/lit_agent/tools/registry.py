"""工具注册表（guide §9）：`Tool` 协议 + 重名保护 + 调用信封。

工具 = **原子能力**（一次 HTTP、一次读文件）；编排策略属于 agent，不写进工具。
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any

from lit_agent.errors import E_SRC_TIMEOUT, E_UNEXPECTED, LitError

__all__ = ["Tool", "ToolRegistry", "ToolResult"]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: Any = None
    error_code: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    run: Callable[..., Any]
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 30.0

    def __call__(self, **kwargs: Any) -> ToolResult:
        # P2：工具级超时必须变成**可读错误**回给调用方，而不是挂死整个 run（DSH timeout-policy）
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(lambda: self.run(**kwargs))
        try:
            return ToolResult(ok=True, output=future.result(timeout=self.timeout_s))
        except FuturesTimeout:
            return ToolResult(
                ok=False,
                error_code=E_SRC_TIMEOUT,
                meta={"timeout_s": self.timeout_s, "tool": self.name},
            )
        except LitError as exc:
            return ToolResult(ok=False, error_code=exc.code, meta={"message": exc.message})
        except Exception as exc:  # noqa: BLE001 - 工具失败要变成结构化结果，不能炸掉调用方
            return ToolResult(
                ok=False,
                error_code=E_UNEXPECTED,
                meta={"message": f"{type(exc).__name__}: {str(exc)[:200]}"},
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise LitError(E_UNEXPECTED, "工具必须有 name")
        if tool.name in self._tools:
            raise LitError(E_UNEXPECTED, f"工具重名：{tool.name}", context={"tool": tool.name})
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise LitError(
                E_UNEXPECTED, f"未知工具：{name}", context={"known": sorted(self._tools)}
            )
        return tool

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        return self.get(name)(**kwargs)

    def __len__(self) -> int:
        return len(self._tools)
