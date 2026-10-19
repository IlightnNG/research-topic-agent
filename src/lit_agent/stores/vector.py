"""Qdrant local（嵌入式）向量存储 + 嵌入器（ADR-0004）。

约定
- **部署形态**：`QdrantClient(path=...)`，进程内、无 server；同一进程只允许一个实例
  （local 模式对目录加锁），故用 `get_client()` 做单例。
- **契约**：collection `size=1024`、`Cosine`、payload 六字段（guide §2.6，逐字）。
- **身份**：`store_meta` 记录 `model_id / model_rev / dim / active_collection`；
  不一致即 `E_VECTOR_MODEL_MISMATCH` / `E_VECTOR_DIM_MISMATCH`（禁止静默混用）。
- **嵌入器可注入**：`Embedder` 协议 + `HashingEmbedder`（确定性、离线、测试/降级用）
  + `SentenceTransformerEmbedder`（真实 bge-m3，懒加载）。
"""

from __future__ import annotations

import atexit
import hashlib
import math
import uuid
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    Range,
    VectorParams,
)

from lit_agent.config import Settings
from lit_agent.errors import (
    E_VECTOR_COLLECTION_MISSING,
    E_VECTOR_DIM_MISMATCH,
    E_VECTOR_MODEL_MISMATCH,
    LitError,
)
from lit_agent.selftest import assert_ascii_path, read_store_meta

__all__ = [
    "CONTRACT_DIM",
    "Embedder",
    "HashingEmbedder",
    "SentenceTransformerEmbedder",
    "VectorStore",
    "get_client",
    "paper_text",
]

CONTRACT_DIM = 1024  # guide §2.6 冻结值

_CLIENTS: dict[str, QdrantClient] = {}


class Embedder(Protocol):
    """嵌入器契约：`dim` 必须等于 collection 维度，`model_id/model_rev` 用于身份校验。"""

    model_id: str
    model_rev: str
    dim: int

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> list[list[float]]: ...


class HashingEmbedder:
    """确定性 1024 维哈希嵌入（离线、零依赖）。

    用途：①测试替身（不下载 2.27 GB 模型）；②ADR-0004 的**降级方案 C**（模型不可用时）。
    它没有任何语义能力——检索质量等同于词袋哈希，**不得**用它做语义结论。
    """

    model_id = "local/hashing-1024"
    model_rev = "v1"

    def __init__(self, dim: int = CONTRACT_DIM) -> None:
        self.dim = dim

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = text.lower().split()
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbedder:
    """真实模型（默认 `BAAI/bge-m3`）。**懒加载**：import 与权重加载都在首次 encode 时发生。"""

    def __init__(
        self,
        model_id: str = "BAAI/bge-m3",
        *,
        model_rev: str = "",
        dim: int = CONTRACT_DIM,
        num_threads: int = 8,
        device: str = "cpu",
    ) -> None:
        self.model_id = model_id
        self.model_rev = model_rev or "unpinned"
        self.dim = dim
        self._num_threads = num_threads
        self._device = device
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(max(1, int(self._num_threads)))
        kwargs: dict[str, Any] = {"device": self._device}
        if self.model_rev not in ("", "unpinned"):
            kwargs["revision"] = self.model_rev
        model = SentenceTransformer(self.model_id, **kwargs)
        model.eval()
        # sentence-transformers 6.x 改名：新方法优先，旧方法兜底
        getter = (
            getattr(model, "get_embedding_dimension", None)
            or model.get_sentence_embedding_dimension
        )
        actual = int(getter() or 0)
        if actual != self.dim:
            raise LitError(
                E_VECTOR_DIM_MISMATCH,
                f"模型 {self.model_id} 维度 {actual} != 契约 {self.dim}",
                context={"model_id": self.model_id, "actual": actual, "expected": self.dim},
            )
        self._model = model
        return model

    def encode(self, texts: Sequence[str], *, batch_size: int = 32) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [list(map(float, row)) for row in vectors]


def get_client(path: Path) -> QdrantClient:
    """按路径复用 client（local 模式对目录加锁，重复打开会报错）。"""
    key = str(path)
    if key not in _CLIENTS:
        path.mkdir(parents=True, exist_ok=True)
        _CLIENTS[key] = QdrantClient(path=key)
        # qdrant-client 的 __del__ 在解释器关闭阶段会 ImportError；提前 atexit 关闭。
        atexit.register(close_clients)
    return _CLIENTS[key]


def close_clients() -> None:
    import contextlib

    for client in list(_CLIENTS.values()):
        with contextlib.suppress(Exception):  # 关闭失败不影响退出
            client.close()
    _CLIENTS.clear()


def paper_text(row: dict[str, Any]) -> str:
    """嵌入文本 = 标题 + 空行 + 摘要（ADR-0004 §5.3）。"""
    title = str(row.get("title") or "")
    abstract = str(row.get("abstract") or "")
    return f"{title}\n\n{abstract}".strip()


def _point_id(paper_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"lit-agent:paper:{paper_id}"))


class VectorStore:
    """`papers_v1` collection 的读写封装（payload 严格按 §2.6）。"""

    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        *,
        collection: str | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings
        self.embedder = embedder
        self.collection = collection or settings.vector.active_collection
        self.client = client or get_client(
            assert_ascii_path(settings.storage.qdrant_dir, label="storage.qdrant_path")
        )

    # ------------------------------------------------------------------ #
    # 生命周期与身份
    # ------------------------------------------------------------------ #
    @classmethod
    def open(
        cls, settings: Settings, embedder: Embedder | None = None, **kwargs: Any
    ) -> VectorStore:
        store = cls(settings, embedder or build_embedder(settings), **kwargs)
        store.ensure_collection()
        store.check_identity()
        return store

    def ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection not in existing:
            self.client.create_collection(
                self.collection,
                vectors_config=VectorParams(size=self.embedder.dim, distance=Distance.COSINE),
            )
            # 注意：Qdrant **local** 不支持 payload 索引（官方警告为 no-op），
            # 因此这里不建索引；换 server 形态时（ADR-0004 §3.2 复评）再加。

    def check_identity(self) -> None:
        """三重一致性：模型维度 == 契约维度 == collection 维度 == store_meta.dim。"""
        if self.embedder.dim != CONTRACT_DIM:
            raise LitError(
                E_VECTOR_DIM_MISMATCH,
                f"embedder.dim={self.embedder.dim} != 契约 {CONTRACT_DIM}",
                context={"model_id": self.embedder.model_id},
            )
        if self.collection not in {c.name for c in self.client.get_collections().collections}:
            raise LitError(
                E_VECTOR_COLLECTION_MISSING,
                f"collection 不存在：{self.collection}",
                context={"collection": self.collection},
            )
        info = self.client.get_collection(self.collection)
        size = info.config.params.vectors.size  # type: ignore[union-attr]
        if int(size) != CONTRACT_DIM:
            raise LitError(
                E_VECTOR_DIM_MISMATCH,
                f"collection 维度 {size} != 契约 {CONTRACT_DIM}",
                context={"collection": self.collection, "actual": int(size)},
            )
        meta = read_store_meta(self.settings.storage.sqlite_file).get("qdrant")
        if meta:
            recorded_model = str(meta.get("model_id") or "")
            recorded_rev = str(meta.get("model_rev") or "")
            if recorded_model and recorded_model != self.embedder.model_id:
                raise LitError(
                    E_VECTOR_MODEL_MISMATCH,
                    f"向量库由 {recorded_model} 建立，当前嵌入器为 {self.embedder.model_id}；"
                    "请走 ADR-0004 §8 的重嵌入流程",
                    context={"recorded": recorded_model, "current": self.embedder.model_id},
                )
            if recorded_rev and recorded_rev != self.embedder.model_rev:
                raise LitError(
                    E_VECTOR_MODEL_MISMATCH,
                    f"向量库模型版本 {recorded_rev} != 当前 {self.embedder.model_rev}",
                    context={"recorded": recorded_rev, "current": self.embedder.model_rev},
                )

    # ------------------------------------------------------------------ #
    # 写入与检索
    # ------------------------------------------------------------------ #
    def upsert_papers(
        self, rows: Sequence[dict[str, Any]], *, topic_ids: Sequence[str] = ()
    ) -> int:
        """幂等写入：point id 由 `paper_id` 派生，重复写不会产生新点。"""
        if not rows:
            return 0
        texts = [paper_text(row) for row in rows]
        vectors = self.embedder.encode(texts, batch_size=self.settings.vector.batch_size)
        points = []
        for row, vector in zip(rows, vectors, strict=True):
            points.append(
                PointStruct(
                    id=_point_id(str(row["paper_id"])),
                    vector=[float(value) for value in vector],
                    payload={
                        "paper_id": row["paper_id"],
                        "title": row.get("title"),
                        "year": row.get("year"),
                        "source": row.get("source"),
                        "topic_ids": list(topic_ids),
                        "published_at": row.get("published_at"),
                        "discovered_at": row.get("discovered_at"),
                    },
                )
            )
        self.client.upsert(self.collection, points=points)
        return len(points)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        year_from: int | None = None,
        paper_ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.encode([query])[0]
        conditions = []
        if year_from is not None:
            conditions.append(FieldCondition(key="year", range=Range(gte=year_from)))
        if paper_ids is not None:
            conditions.append(FieldCondition(key="paper_id", match=MatchAny(any=list(paper_ids))))
        query_filter = Filter(must=conditions) if conditions else None
        result = self.client.query_points(
            self.collection, query=vector, limit=limit, query_filter=query_filter
        )
        return [
            {
                "paper_id": point.payload.get("paper_id"),
                "score": float(point.score),
                "payload": dict(point.payload or {}),
            }
            for point in result.points
        ]

    def count(self) -> int:
        return int(self.client.count(self.collection, exact=True).count)

    def close(self) -> None:
        """local 模式没有 per-store close；进程退出前由 `close_clients()` 统一关闭。"""
        return None


def build_embedder(settings: Settings, *, force_hashing: bool = False) -> Embedder:
    """按 ADR-0004 构造嵌入器：默认真实模型；`force_hashing` 或显式配置时用确定性降级。"""
    if force_hashing or settings.vector.model_id.startswith("local/"):
        return HashingEmbedder(settings.vector.dim)
    return SentenceTransformerEmbedder(
        settings.vector.model_id,
        model_rev=settings.vector.model_rev,
        dim=settings.vector.dim,
        num_threads=settings.vector.num_threads,
    )


def identity_fields(embedder: Embedder, collection: str) -> dict[str, Any]:
    """写入 `store_meta` 的向量库身份字段。"""
    return {
        "model_id": embedder.model_id,
        "model_rev": embedder.model_rev,
        "dim": embedder.dim,
        "active_collection": collection,
    }


def iter_batches(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
