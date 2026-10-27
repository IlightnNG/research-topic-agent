"""Surface checks: packages import, skeletons fail explicitly, contracts are models."""

from __future__ import annotations

import importlib
from enum import Enum

import pytest
from pydantic import BaseModel

from lit_agent import models, structure
from lit_agent.db import tables

PACKAGES = [name for name in structure.PACKAGES if name != "."]


@pytest.mark.parametrize("package", PACKAGES)
def test_every_package_is_importable(package: str) -> None:
    module = importlib.import_module("lit_agent." + package.replace("/", "."))
    assert module is not None


def test_every_expected_module_file_imports() -> None:
    for rel in structure.expected_files():
        if not rel.endswith(".py") or rel.endswith("__main__.py"):
            continue
        dotted = rel[:-3].replace("/", ".")
        if dotted.endswith(".__init__"):
            dotted = dotted[: -len(".__init__")]
        importlib.import_module("lit_agent." + dotted)


def test_skeleton_entry_points_fail_explicitly() -> None:
    from lit_agent.agents import chat
    from lit_agent.graph import edges

    assert edges.backoff_edge("E11") == "replan"
    with pytest.raises(ValueError):
        edges.backoff_edge("E99")

    # Chat 已在 3.3 实装；这里校验它不再以 skeleton 方式报错
    assert chat.CHAT_GOAL.autonomy == "L3"
    assert callable(chat.answer)


def test_skeleton_modules_declare_feature_id() -> None:
    checked = 0
    for rel in structure.expected_files():
        if not rel.endswith(".py") or rel.endswith("__init__.py"):
            continue
        module = importlib.import_module("lit_agent." + rel[:-3].replace("/", "."))
        if hasattr(module, "FEATURE"):
            checked += 1
            assert isinstance(module.FEATURE, str) and module.FEATURE
    assert checked >= 1, f"skeleton module count looks wrong: {checked}"


def test_models_public_names_are_contract_models() -> None:
    names = [name for name in models.__all__ if name != "format_validation"]
    for name in names:
        obj = getattr(models, name)
        assert isinstance(obj, type), f"{name} is not a type"
        if name == "RunId":
            assert obj is str
            continue
        assert issubclass(obj, (BaseModel, Enum)), f"{name} is neither a model nor an enum"
    assert models.ContractModel.model_config["extra"] == "forbid"
    assert models.ContractModel.model_config["frozen"] is True


def test_schema_version_is_single_source() -> None:
    assert structure.SCHEMA_VERSION == tables.SCHEMA_VERSION


def test_expected_table_count_is_26() -> None:
    assert len(tables.EXPECTED_TABLES) == 26, sorted(tables.EXPECTED_TABLES)
