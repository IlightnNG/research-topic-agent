"""Tool Platform package (migration target)."""

from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.schema import validate_args

__all__ = ["ToolRegistry", "validate_args"]
