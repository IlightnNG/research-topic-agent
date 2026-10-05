"""单一版本来源。

独立成模块，供 `__init__` 与 `logging` 等模块引用，避免循环导入。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.3.0"
