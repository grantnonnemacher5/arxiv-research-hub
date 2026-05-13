"""Bucket labels: OpenAI embeddings + cosine similarity when a key is set; otherwise keyword heuristics (no API)."""

from __future__ import annotations

import logging
import re
from typing import Iterable

import numpy as np
from openai import OpenAI

from config import (
    CLASSIFIER_THRESHOLD,
    CLASSIFY_FROM_ABSTRACT,
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
_bucket_keyword_sets: dict[str, set[str]] | None = None
_logged_keyword_classifier = False


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


def classification_input_text(full_text: str | None, abstract: str) -> str:
    """Text used for bucket labels (abstract-only when CLASSIFY_FROM_ABSTRACT)."""
    if CLASSIFY_FROM_ABSTRACT:
        return (abstract or "").strip()[:12000]
    return paper_text_for_embedding(full_text, abstract)


def _ensure_bucket_keyword_sets() -> dict[str, set[str]]:
    """Lowercase keywords/phrases derived from bucket descriptions + a few hand-picked hints."""
    global _bucket_keyword_sets
    if _bucket_keyword_sets is not None:
        return _bucket_keyword_sets
    extras: dict[str, set[str]] = {
        "General AI": {
            "llm", "gpt", "transformer", "neural", "network", "pytorch", "tensorflow",
            "attention", "diffusion", "vision", "classification", "segmentation",
        },
        "Autonomous Agents": {
            "agent", "agents", "multi-agent", "reinforcement", "policy", "planning",
            "decision", "autonomous", "robot", "tool", "orchestration",
        },
        "AI x Finance": {
            "portfolio", "trading", "market", "risk", "equity", "asset", "pricing",
            "volatility", "derivative", "hedge", "return", "forecast", "credit",
        },
    }
    out: dict[str, set[str]] = {}
    for name, desc in BUCKET_DESCRIPTIONS.items():
        words = set(re.findall(r"[a-z]{4,}", desc.lower()))
        words |= extras.get(name, set())
        out[name] = words
    _bucket_keyword_sets = out
    return out


def classify_paper_text_keyword(text: str) -> tuple[list[str], bytes]:
    """
    Assign buckets from keyword overlap with theme text (no network, no embeddings).
    Returns ([labels], b'') — embedding bytes empty until OpenAI path runs.
    """
    global _logged_keyword_classifier
    if not _logged_keyword_classifier:
        logger.info("Using keyword-only bucket classifier (OPENAI_API_KEY unset)")
        _logged_keyword_classifier = True
    hay = text.lower()
    scored: list[tuple[str, float, int]] = []
    for name, kws in _ensure_bucket_keyword_sets().items():
        hits = sum(1 for w in kws if w in hay)
        norm = hits / (len(kws) ** 0.5 + 0.01)
        scored.append((name, float(norm), hits))
    scored.sort(key=lambda x: -x[1])
    best_name, best_s, best_hits = scored[0]
    if best_hits == 0:
        return [best_name], b""
    rel = 0.55
    labels = [n for n, s, h in scored if h > 0 and s >= best_s * rel]
    if not labels:
        labels = [best_name]
    return labels, b""


def _classify_paper_text_openai(text: str) -> tuple[list[str], bytes]:
    paper_vec = np.asarray(_embed_batch([text[:12000]])[0], dtype=np.float64)
    buckets = _ensure_bucket_vectors()
    labels = _labels_for_paper_vector(paper_vec, buckets)
    emb_bytes = paper_vec.astype(np.float32).tobytes()
    return labels, emb_bytes


def classify_paper_text(text: str) -> tuple[list[str], bytes]:
    """
    Returns (bucket names, float32 embedding bytes for the paper text).
    With OPENAI_API_KEY: OpenAI embeddings + cosine vs bucket vectors.
    Without key: keyword overlap heuristics, empty embedding bytes.
    """
    text = (text or "").strip()
    if not text:
        return [], b""
    if OPENAI_API_KEY:
        return _classify_paper_text_openai(text)
    return classify_paper_text_keyword(text)


def buckets_to_csv(labels: Iterable[str]) -> str:
    return ", ".join(dict.fromkeys(labels))


def embedding_from_blob(blob: bytes | None) -> np.ndarray | None:
    if not blob:
        return None
    return np.frombuffer(blob, dtype=np.float32)


def embed_query_text(text: str) -> np.ndarray:
    """Single query vector for semantic / hybrid search (same model as paper classification)."""
    t = (text or "").strip()[:12000]
    if not t:
        raise ValueError("Search query is empty")
    return np.asarray(_embed_batch([t])[0], dtype=np.float64)
