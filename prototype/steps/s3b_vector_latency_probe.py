"""S3 补充探针：向量 top-10 延迟归因（回答"155ms 是设计问题还是优化/测法问题"）。

背景：S3 全量测得 `vector_top10_filtered` p95 = 155.45 ms，未达 p95 ≤ 100 ms 的验收目标。
但那次用的是 **Qdrant local（嵌入式）模式**，而读源码发现 local 模式
（`qdrant_client/local/local_collection.py`）中 `HNSW` 出现 0 次、`np.dot` 0 次
—— 它没有 ANN 索引，是 Python/numpy 逐点扫描 + Python 层 payload 过滤。

本探针把 ~150 ms 拆成可归因的部分，并测出随规模的伸缩（用于 2 万篇外推）：
  1. **纯算力下限**：numpy 暴力点积 + argsort（完全不经过 Qdrant 代码）；
  2. **local 模式开销**：同样查询走 QdrantLocal 相对纯 numpy 的差值；
  3. **过滤成本**：无过滤 / 单条件 / 双条件（= S3 基线测法）的差值，并记录过滤命中基数；
  4. **payload 索引是否有效**：local 模式建索引前后对比；
  5. **规模曲线**：1250 / 2500 / 5000 点下的基线延迟与算力下限。

口径：写入路径**直接复用 S3 的函数**（`init_qdrant` / `qdrant_upsert`），保证与 S3 基线可比。
产出：`out/s3b_vector_latency.json`。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from lit_agent_min import load_settings  # noqa: E402
from steps.s3_storage_spike import (  # noqa: E402
    VECTOR_DIM,
    build_dataset,
    init_qdrant,
    load_real_records,
    pseudo_vector,
    qdrant_upsert,
    reset_store_path,
)

SIZES = (1250, 2500, 5000)
SIZES_ROUNDS = 20
DETAIL_ROUNDS = 30
PAPERS = 5000


def measure(fn: Any, rounds: int) -> dict[str, Any]:
    lat: list[float] = []
    errors = 0
    for _ in range(rounds):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception:  # noqa: BLE001
            errors += 1
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    return {
        "rounds": rounds,
        "errors": errors,
        "p50_ms": round(median(lat), 2),
        "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 2),
        "max_ms": round(max(lat), 2),
    }


def numpy_floor(rows: list[dict[str, Any]], probe: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    matrix = np.asarray([pseudo_vector(r["paper_id"]) for r in rows], dtype=np.float32)
    sub = matrix[mask]
    out = {
        "matrix_mb": round(matrix.nbytes / 1_048_576, 2),
        "filtered_rows": int(sub.shape[0]),
        "scores_only": measure(lambda: matrix @ probe, DETAIL_ROUNDS),
        "top10_full_scan": measure(lambda: np.argsort(-(matrix @ probe))[:10], DETAIL_ROUNDS),
        "top10_filtered_subset": measure(lambda: np.argsort(-(sub @ probe))[:10], DETAIL_ROUNDS),
    }
    return out


def main() -> int:
    from qdrant_client.models import (
        FieldCondition,
        Filter,
        MatchValue,
        PayloadSchemaType,
        Range,
    )

    settings = load_settings()
    dataset = build_dataset(load_real_records(settings.paths.out_dir), PAPERS)
    probe = np.asarray(pseudo_vector(dataset[0]["paper_id"]), dtype=np.float32)
    print(f"dataset={len(dataset)} dim={VECTOR_DIM}")

    base_path = settings.paths.out_dir / "data" / "qdrant_diag"
    f_topic = Filter(must=[FieldCondition(key="topic_ids", match=MatchValue(value="T1"))])
    f_year = Filter(must=[FieldCondition(key="year", range=Range(gte=2020))])
    f_both = Filter(
        must=[
            FieldCondition(key="topic_ids", match=MatchValue(value="T1")),
            FieldCondition(key="year", range=Range(gte=2020)),
        ]
    )

    out: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "probe_note": "写入路径复用 S3 的 init_qdrant/qdrant_upsert，保证与 S3 基线同口径",
        "vector_dim": VECTOR_DIM,
        "detail_rounds": DETAIL_ROUNDS,
        "sizes_rounds": SIZES_ROUNDS,
        "scale": {},
        "detail": {},
    }

    # ---------- 规模曲线：每个规模一个干净 collection ----------
    for size in SIZES:
        rows = dataset[:size]
        reset_store_path(base_path / f"n{size}")
        (base_path / f"n{size}").mkdir(parents=True, exist_ok=True)
        client, notes = init_qdrant(base_path / f"n{size}")
        qdrant_upsert(client, rows)
        mask = np.asarray([(r["topic"] == "T1" and (r["year"] or 0) >= 2020) for r in rows])
        entry = {
            "points": client.count("papers").count,
            "filtered_rows": int(mask.sum()),
            "notes": notes,
            "local_filter_both_top10": measure(
                lambda c=client: c.query_points(
                    "papers", query=probe.tolist(), query_filter=f_both, limit=10
                ),
                SIZES_ROUNDS,
            ),
            "numpy": numpy_floor(rows, probe, mask),
        }
        out["scale"][str(size)] = entry
        client.close()
        print(
            f"  n={size:5d} points={entry['points']} filtered={entry['filtered_rows']} "
            f"local_p50={entry['local_filter_both_top10']['p50_ms']}ms "
            f"numpy_p50={entry['numpy']['top10_full_scan']['p50_ms']}ms"
        )

    # ---------- 明细：5000 点下拆解过滤与索引成本 ----------
    reset_store_path(base_path / "detail")
    (base_path / "detail").mkdir(parents=True, exist_ok=True)
    client, _ = init_qdrant(base_path / "detail")
    qdrant_upsert(client, dataset)
    qvec = probe.tolist()
    detail = out["detail"]
    detail["points"] = client.count("papers").count
    detail["filter_cardinality"] = {
        "topic_T1": client.count("papers", count_filter=f_topic).count,
        "year_ge_2020": client.count("papers", count_filter=f_year).count,
        "both": client.count("papers", count_filter=f_both).count,
        "total": client.count("papers").count,
    }
    detail["local_unfiltered_top10"] = measure(
        lambda: client.query_points("papers", query=qvec, limit=10), DETAIL_ROUNDS
    )
    detail["local_filter_topic_top10"] = measure(
        lambda: client.query_points("papers", query=qvec, query_filter=f_topic, limit=10),
        DETAIL_ROUNDS,
    )
    detail["local_filter_year_top10"] = measure(
        lambda: client.query_points("papers", query=qvec, query_filter=f_year, limit=10),
        DETAIL_ROUNDS,
    )
    detail["local_filter_both_top10"] = measure(  # S3 基线测法
        lambda: client.query_points("papers", query=qvec, query_filter=f_both, limit=10),
        DETAIL_ROUNDS,
    )
    detail["local_filter_both_top100"] = measure(
        lambda: client.query_points("papers", query=qvec, query_filter=f_both, limit=100),
        DETAIL_ROUNDS,
    )
    detail["local_retrieve_by_id"] = measure(
        lambda: client.retrieve("papers", ids=[abs(hash(dataset[0]["paper_id"])) % (2**53)]),
        DETAIL_ROUNDS,
    )

    index_note: list[str] = []
    for field, schema in (
        ("topic_ids", PayloadSchemaType.KEYWORD),
        ("year", PayloadSchemaType.INTEGER),
    ):
        try:
            client.create_payload_index("papers", field_name=field, field_schema=schema)
            index_note.append(f"{field}: created")
        except Exception as exc:  # noqa: BLE001
            index_note.append(f"{field}: failed -> {str(exc)[:80]}")
    detail["payload_index_created"] = index_note
    detail["local_filter_both_top10_after_index"] = measure(
        lambda: client.query_points("papers", query=qvec, query_filter=f_both, limit=10),
        DETAIL_ROUNDS,
    )
    client.close()

    out_path = settings.paths.out_dir / "s3b_vector_latency.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 明细（5000 点）===")
    print(f"  过滤命中基数: {detail['filter_cardinality']}")
    for name, s in detail.items():
        if isinstance(s, dict) and "p50_ms" in s:
            print(f"  {name:42s} p50={s['p50_ms']:8.2f} p95={s['p95_ms']:8.2f} err={s['errors']}")
    print(f"  payload_index: {index_note}")
    print("\n=== 规模曲线 ===")
    for size, e in out["scale"].items():
        print(
            f"  n={size:>5} local_p50={e['local_filter_both_top10']['p50_ms']:7.2f}ms "
            f"numpy_floor_p50={e['numpy']['top10_filtered_subset']['p50_ms']:5.2f}ms "
            f"matrix={e['numpy']['matrix_mb']}MB"
        )
    print(f"\nsummary: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
