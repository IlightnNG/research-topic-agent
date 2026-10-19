"""嵌入器（ADR-0004）：确定性哈希降级版的性质。"""

from __future__ import annotations

import math

from lit_agent.stores.vector import CONTRACT_DIM, HashingEmbedder


def test_dimension_matches_contract() -> None:
    embedder = HashingEmbedder()
    assert embedder.dim == CONTRACT_DIM == 1024
    vectors = embedder.encode(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 1024


def test_vectors_are_unit_normalized() -> None:
    embedder = HashingEmbedder()
    vector = embedder.encode(["llm agent planning tool use"])[0]
    norm = math.sqrt(sum(value * value for value in vector))
    assert abs(norm - 1.0) < 1e-6


def test_encoding_is_deterministic() -> None:
    embedder = HashingEmbedder()
    a = embedder.encode(["same text"])
    b = embedder.encode(["same text"])
    assert a == b


def test_different_text_differs() -> None:
    embedder = HashingEmbedder()
    a = embedder.encode(["llm agents"])[0]
    b = embedder.encode(["wireless networks"])[0]
    assert a != b


def test_empty_text_is_handled() -> None:
    embedder = HashingEmbedder()
    vector = embedder.encode([""])[0]
    assert len(vector) == 1024
    assert abs(sum(value * value for value in vector) - 1.0) < 1e-6


def test_identity_fields_are_declared() -> None:
    embedder = HashingEmbedder()
    assert embedder.model_id.startswith("local/")
    assert embedder.model_rev
