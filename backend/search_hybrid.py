"""Keyword + dense (embedding) search with RRF fusion; optional token-overlap rerank.

Uses embeddings already stored on `Paper` rows (no external vector DB for MVP).
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from classifier import (
    cosine_similarity,
    embed_query_text,
    embedding_from_blob,
)
from config import (
    OPENAI_API_KEY,
    SEARCH_KEYWORD_POOL,
    SEARCH_RRF_K,
    SEARCH_SEMANTIC_MAX_PAPERS,
)
from database import Paper

logger = logging.getLogger(__name__)


def _bucket_filter_stmt(stmt, bucket: str | None):
    if bucket and bucket.strip():
        return stmt.where(Paper.buckets.contains(bucket.strip()))
    return stmt


def _keyword_candidates(db: Session, needle: str, bucket: str | None) -> list[Paper]:
    n = needle.strip()[:500]
    stmt = select(Paper).order_by(Paper.created_at.desc())
    stmt = _bucket_filter_stmt(stmt, bucket)
    search = or_(
        Paper.title.contains(n),
        Paper.authors.contains(n),
        Paper.abstract.contains(n),
        Paper.arxiv_id.contains(n),
    )
    stmt = stmt.where(search)
    return list(db.scalars(stmt.limit(SEARCH_KEYWORD_POOL)).all())


def _semantic_ranked(
    db: Session, query_vec: np.ndarray, bucket: str | None
) -> list[tuple[Paper, float]]:
    stmt = select(Paper).where(Paper.embedding.isnot(None))
    stmt = _bucket_filter_stmt(stmt, bucket)
    rows = list(db.scalars(stmt).all())
    if len(rows) > SEARCH_SEMANTIC_MAX_PAPERS:
        rows.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        rows = rows[:SEARCH_SEMANTIC_MAX_PAPERS]

    scored: list[tuple[Paper, float]] = []
    for p in rows:
        vec = embedding_from_blob(p.embedding)
        if vec is None:
            continue
        paper64 = vec.astype(np.float64)
        sim = cosine_similarity(query_vec, paper64)
        scored.append((p, sim))
    scored.sort(key=lambda x: -x[1])
    return scored


def _rrf_merge(
    keyword_order: list[Paper],
    semantic_order: list[Paper],
    k: int,
) -> list[tuple[Paper, float]]:
    scores: dict[int, float] = defaultdict(float)
    for i, p in enumerate(keyword_order):
        scores[p.id] += 1.0 / (k + i + 1)
    for i, p in enumerate(semantic_order):
        scores[p.id] += 1.0 / (k + i + 1)
    by_id: dict[int, Paper] = {p.id: p for p in keyword_order}
    for p in semantic_order:
        by_id.setdefault(p.id, p)
    merged = sorted(by_id.values(), key=lambda p: -scores.get(p.id, 0.0))
    return [(p, scores[p.id]) for p in merged]


def _keyword_overlap_score(needle: str, paper: Paper) -> float:
    tokens = [t for t in re.split(r"\W+", needle.lower()) if len(t) > 1]
    if not tokens:
        return 0.0
    hay = f"{paper.title} {paper.abstract}".lower()
    hits = sum(1 for t in tokens if t in hay)
    return hits / len(tokens)


def _rerank_fusion(
    fused: list[tuple[Paper, float]],
    query_vec: np.ndarray,
    needle: str,
    out_limit: int,
) -> list[tuple[Paper, dict[str, float]]]:
    rescored: list[tuple[Paper, dict[str, float]]] = []
    for p, fusion in fused:
        vec = embedding_from_blob(p.embedding)
        if vec is not None:
            sem = cosine_similarity(query_vec, vec.astype(np.float64))
            sem_n = (sem + 1.0) / 2.0
        else:
            sem_n = 0.0
        kw = _keyword_overlap_score(needle, p)
        combined = 0.62 * sem_n + 0.38 * kw
        rescored.append(
            (
                p,
                {
                    "fusion_rrf": round(fusion, 6),
                    "semantic": round(sem_n, 4),
                    "keyword": round(kw, 4),
                    "rerank": round(combined, 4),
                },
            )
        )
    rescored.sort(key=lambda x: -x[1]["rerank"])
    return rescored[:out_limit]


def run_search(
    db: Session,
    q: str,
    mode: str,
    bucket: str | None,
    limit: int,
    rerank: bool,
) -> dict[str, Any]:
    needle = q.strip()
    if not needle:
        raise ValueError("q must not be empty")

    if mode == "keyword":
        kws = _keyword_candidates(db, needle, bucket)
        items = []
        for p in kws[:limit]:
            items.append(
                {
                    "paper": _paper_dict(p),
                    "scores": {"keyword": round(_keyword_overlap_score(needle, p), 4)},
                }
            )
        return {"mode": mode, "q": needle, "bucket": bucket, "rerank": False, "items": items}

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for semantic and hybrid search")

    query_vec = embed_query_text(needle)

    if mode == "semantic":
        ranked = _semantic_ranked(db, query_vec, bucket)
        items = []
        for p, sim in ranked[:limit]:
            sem_n = (sim + 1.0) / 2.0
            items.append(
                {
                    "paper": _paper_dict(p),
                    "scores": {"semantic": round(sem_n, 4), "cosine": round(sim, 4)},
                }
            )
        return {"mode": mode, "q": needle, "bucket": bucket, "rerank": False, "items": items}

    # hybrid
    kws = _keyword_candidates(db, needle, bucket)
    sem_ranked = _semantic_ranked(db, query_vec, bucket)
    sem_order = [p for p, _ in sem_ranked]
    fused = _rrf_merge(kws, sem_order, SEARCH_RRF_K)

    if rerank and fused:
        top_pool = min(len(fused), max(limit * 4, 40))
        reranked = _rerank_fusion(fused[:top_pool], query_vec, needle, limit)
        items = [{"paper": _paper_dict(p), "scores": sc} for p, sc in reranked]
    else:
        items = []
        for p, fusion in fused[:limit]:
            vec = embedding_from_blob(p.embedding)
            sem = (
                cosine_similarity(query_vec, vec.astype(np.float64))
                if vec is not None
                else 0.0
            )
            items.append(
                {
                    "paper": _paper_dict(p),
                    "scores": {
                        "fusion_rrf": round(fusion, 6),
                        "semantic": round((sem + 1.0) / 2.0, 4),
                        "keyword": round(_keyword_overlap_score(needle, p), 4),
                    },
                }
            )

    return {"mode": mode, "q": needle, "bucket": bucket, "rerank": bool(rerank), "items": items}


def _paper_dict(p: Paper) -> dict[str, Any]:
    return {
        "id": p.id,
        "arxiv_id": p.arxiv_id,
        "title": p.title,
        "authors": p.authors,
        "abstract": (ab := (p.abstract or ""))[:500] + ("…" if len(ab) > 500 else ""),
        "published_date": p.published_date.isoformat() if p.published_date else None,
        "buckets": p.buckets,
        "pdf_url": p.pdf_url,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
