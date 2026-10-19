"""指标导出：JSON / CSV / Markdown（结果可粘贴进周报与论文附表）。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

__all__ = ["export_metrics"]

_FIELDS = (
    "scope",
    "scope_id",
    "papers",
    "paper_merges",
    "claims",
    "grounding_rate",
    "hallucination_rate",
    "citation_coverage",
    "dedup_rate",
    "cost_usd",
    "cost_estimated_calls",
)


def export_metrics(rows: list[dict[str, Any]], path: str | Path, *, fmt: str | None = None) -> Path:
    """把指标行写成文件；格式由 `fmt` 或扩展名决定（json/csv/md）。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    kind = (fmt or target.suffix.lstrip(".")).lower()

    if kind == "json":
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif kind == "csv":
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(_FIELDS), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    elif kind in ("md", "markdown"):
        header = "| " + " | ".join(_FIELDS) + " |"
        divider = "|" + "---|" * len(_FIELDS)
        lines = ["# Metrics", "", header, divider]
        for row in rows:
            cells = [str(row.get(field, "")) for field in _FIELDS]
            lines.append("| " + " | ".join(cells) + " |")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"不支持的导出格式：{kind}")
    return target
