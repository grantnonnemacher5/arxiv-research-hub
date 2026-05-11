"""OpenAI embeddings + cosine similarity bucket labels (plan Day 2)."""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np
from openai import OpenAI

from config import (
    CLASSIFIER_THRESHOLD,
    OPENAI_API_KEY,
    OPENAI_EMBED_MODEL,
)

logger = logging.getLogger(__name__)

BUCKET_DESCRIPTIONS: dict[str, str] = {
    "General AI": (
        "Large language models, foundation models, deep learning, machine learning, "
        "neural networks, computer vision"
    ),
    "Autonomous Agents": (
        "AI agents, autonomous systems, multi-agent reinforcement learning, "
        "decision making, planning"
    ),
    "AI x Finance": (
        "AI in finance, algorithmic trading, portfolio optimization, risk modeling, "
        "financial NLP, market prediction"
    ),
}

_client: OpenAI | None = None
_bucket_vectors: dict[str, np.ndarray] | None = None


def _get_client() -> OpenAI:
    global _client
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = _get_client()
    resp = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _ensure_bucket_vectors() -> dict[str, np.ndarray]:
    global _bucket_vectors
    if _bucket_vectors is not None:
        return _bucket_vectors
    names = list(BUCKET_DESCRIPTIONS.keys())
    descs = [BUCKET_DESCRIPTIONS[n] for n in names]
    vecs = _embed_batch(descs)
    _bucket_vectors = {
        n: np.asarray(v, dtype=np.float64) for n, v in zip(names, vecs, strict=True)
    }
    return _bucket_vectors


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _labels_for_paper_vector(paper_vec: np.ndarray, buckets: dict[str, np.ndarray]) -> list[str]:
    scored: list[tuple[str, float]] = [
        (name, cosine_similarity(paper_vec, bvec)) for name, bvec in buckets.items()
    ]
    labels = [n for n, s in scored if s >= CLASSIFIER_THRESHOLD]
    if labels:
        return labels
    best_name = max(scored, key=lambda x: x[1])[0]
    return [best_name]


def paper_text_for_embedding(full_text: str | None, abstract: str) -> str:
    raw = (full_text or "").strip() or (abstract or "").strip()
    return raw[:30000]


def classify_paper_text(text: str) -> tuple[list[str], bytes]:
    """
    Returns (bucket names, float32 embedding bytes for the paper text).
    If text is empty, returns ([], b'').
    """
    text = (text or "").strip()
    if not text:
        return [], b""

    paper_vec = np.asarray(_embed_batch([text[:12000]])[0], dtype=np.float64)
    buckets = _ensure_bucket_vectors()
    labels = _labels_for_paper_vector(paper_vec, buckets)
    emb_bytes = paper_vec.astype(np.float32).tobytes()
    return labels, emb_bytes


def buckets_to_csv(labels: Iterable[str]) -> str:
    return ", ".join(dict.fromkeys(labels))


def embedding_from_blob(blob: bytes | None) -> np.ndarray | None:
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.float32)
