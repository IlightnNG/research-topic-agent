"""Evaluation dataset loader.

SKELETON (Phase 1): the interface exists and is importable; the logic lands in a later step.
Every entry point raises FeatureDisabledError so a missing implementation can never look like a success.
"""

from __future__ import annotations

from typing import Any

from lit_agent.errors import FeatureDisabledError

FEATURE = "eval.datasets"


def _ni(name: str) -> FeatureDisabledError:
    return FeatureDisabledError(FEATURE, name + " not implemented yet")


def load_dataset(*args: Any, **kwargs: Any) -> Any:
    raise _ni("load_dataset")
