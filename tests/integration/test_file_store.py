"""文件存储（Step 1.5）：ASCII 安全命名、大小/魔数校验、过期清理。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lit_agent.config import Settings, StorageSettings
from lit_agent.errors import E_SRC_SCHEMA, LitError
from lit_agent.stores.files import paper_path, prune, safe_stem, save_pdf

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def settings_for(tmp_path: Path) -> Settings:
    return Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))


def test_safe_stem_is_ascii_and_stable() -> None:
    doi = "10.1000/abc.def(ghi)"
    stem = safe_stem(doi)
    assert stem.isascii()
    assert "/" not in stem
    assert stem == safe_stem(doi)
    assert stem != safe_stem(doi + "x")


def test_save_pdf_writes_under_papers_dir(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    path = save_pdf(settings, "10.1000/xyz", PDF_BYTES)

    assert path.exists()
    assert path.parent == settings.storage.papers_path
    assert str(path).isascii()


def test_oversize_pdf_is_rejected(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with pytest.raises(LitError) as excinfo:
        save_pdf(settings, "W1", PDF_BYTES, max_mb=0)
    assert excinfo.value.code == E_SRC_SCHEMA


def test_non_pdf_is_rejected(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with pytest.raises(LitError) as excinfo:
        save_pdf(settings, "W1", b"<html>not a pdf</html>")
    assert excinfo.value.code == E_SRC_SCHEMA


def test_prune_removes_only_old_files(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    old = save_pdf(settings, "W-old", PDF_BYTES)
    fresh = save_pdf(settings, "W-new", PDF_BYTES)
    ancient = os.stat(old).st_mtime - 90 * 86400
    os.utime(old, (ancient, ancient))

    removed = prune(settings, keep_days=30)
    assert removed == 1
    assert not old.exists()
    assert fresh.exists()


def test_paper_path_is_pure_function(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    assert paper_path(settings, "W1") == paper_path(settings, "W1")
