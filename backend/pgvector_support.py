"""PostgreSQL pgvector: ANN index for semantic leg of hybrid search at scale.

SQLite and Postgres without the extension keep using in-memory cosine scans on `Paper.embedding` blobs.
"""

from __future__ import annotations

import logging
import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from config import OPENAI_EMBED_DIMENSION

logger = logging.getLogger(__name__)


def _vector_text_literal(arr: np.ndarray) -> str:
    """PostgreSQL `vector` input as bracketed float list (no psycopg2 adapter needed)."""
    return "[" + ",".join(str(float(x)) for x in arr.tolist()) + "]"


def is_postgres_engine(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def ensure_pgvector_schema(engine: Engine) -> bool:
    """
    Create extension, add `embedding_vec`, and HNSW index when on PostgreSQL.
    Returns True if pgvector-backed search can be used after rows are populated.
    """
    if not is_postgres_engine(engine):
        return False
    dim = OPENAI_EMBED_DIMENSION
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'papers' AND column_name = 'embedding_vec'
                    """
                )
            ).fetchone()
            if not row:
                conn.execute(text(f"ALTER TABLE papers ADD COLUMN embedding_vec vector({dim})"))
                conn.commit()
                logger.info("Added papers.embedding_vec vector(%s) for pgvector ANN search", dim)
            else:
                conn.commit()
        with engine.connect() as conn:
            try:
                conn.execute(
                    text(
                        """
                        CREATE INDEX IF NOT EXISTS papers_embedding_vec_hnsw
                        ON papers USING hnsw (embedding_vec vector_cosine_ops)
                        """
                    )
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.warning(
                    "HNSW index on embedding_vec not created (pgvector version or permissions); "
                    "ANN queries still work, may use sequential scan until index is added."
                )
        return True
    except Exception:
        logger.exception("pgvector schema setup failed; semantic search will use in-memory scan")
        return False


def sync_paper_embedding_vec(db: Session, paper_id: int, embedding_blob: bytes | None) -> None:
    """Write float32 blob into `embedding_vec` for ANN queries (PostgreSQL only)."""
    if not embedding_blob:
        return
    bind = db.get_bind()
    if not is_postgres_engine(bind):
        return
    arr = np.frombuffer(embedding_blob, dtype=np.float32)
    if arr.size != OPENAI_EMBED_DIMENSION:
        logger.warning(
            "Embedding length %s != OPENAI_EMBED_DIMENSION %s; skip pgvector sync for paper %s",
            arr.size,
            OPENAI_EMBED_DIMENSION,
            paper_id,
        )
        return
    lit = _vector_text_literal(arr)
    db.execute(
        text("UPDATE papers SET embedding_vec = CAST(:v AS vector) WHERE id = :id"),
        {"v": lit, "id": paper_id},
    )


def count_pgvector_indexed(db: Session) -> int:
    bind = db.get_bind()
    if not is_postgres_engine(bind):
        return 0
    try:
        n = db.scalar(text("SELECT COUNT(*) FROM papers WHERE embedding_vec IS NOT NULL"))
        return int(n or 0)
    except Exception:
        return 0


def semantic_ann_candidates(
    db: Session,
    query_vec: np.ndarray,
    bucket: str | None,
    top_k: int,
) -> list[tuple[int, float]] | None:
    """
    Return up to `top_k` paper ids with cosine distance ascending (best first), or None if unavailable.
    Caller should load `Paper` rows and re-score from blobs for exact cosine in API responses.
    """
    bind = db.get_bind()
    if not is_postgres_engine(bind):
        return None
    if count_pgvector_indexed(db) == 0:
        return None
    q = query_vec.astype(np.float64)
    if q.size != OPENAI_EMBED_DIMENSION:
        logger.warning("Query embedding dim %s != %s", q.size, OPENAI_EMBED_DIMENSION)
        return None
    q32 = q.astype(np.float32)
    lit = _vector_text_literal(q32)
    if bucket and bucket.strip():
        rows = db.execute(
            text(
                """
                SELECT id, (embedding_vec <=> CAST(:qv AS vector)) AS dist
                FROM papers
                WHERE embedding_vec IS NOT NULL
                  AND buckets LIKE :bp
                ORDER BY dist ASC
                LIMIT :lim
                """
            ),
            {"qv": lit, "bp": f"%{bucket.strip()}%", "lim": top_k},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """
                SELECT id, (embedding_vec <=> CAST(:qv AS vector)) AS dist
                FROM papers
                WHERE embedding_vec IS NOT NULL
                ORDER BY dist ASC
                LIMIT :lim
                """
            ),
            {"qv": lit, "lim": top_k},
        ).fetchall()
    # Map cosine distance to similarity-like score for ordering tie-breaks (dense rerank recomputes exact).
    out: list[tuple[int, float]] = []
    for pid, dist in rows:
        try:
            d = float(dist)
        except (TypeError, ValueError):
            continue
        sim = max(-1.0, min(1.0, 1.0 - d))
        out.append((int(pid), sim))
    return out


def backfill_embedding_vec_from_blobs(db: Session, batch_limit: int = 500) -> int:
    """Copy existing float32 `embedding` blobs into `embedding_vec` (Postgres only). Returns rows updated."""
    bind = db.get_bind()
    if not is_postgres_engine(bind):
        return 0
    rows = db.execute(
        text(
            """
            SELECT id, embedding FROM papers
            WHERE embedding IS NOT NULL AND embedding_vec IS NULL
            LIMIT :lim
            """
        ),
        {"lim": batch_limit},
    ).fetchall()
    if not rows:
        return 0
    updated = 0
    for pid, emb_blob in rows:
        if not emb_blob:
            continue
        raw = bytes(emb_blob) if not isinstance(emb_blob, (bytes, bytearray)) else emb_blob
        arr = np.frombuffer(raw, dtype=np.float32)
        if arr.size != OPENAI_EMBED_DIMENSION:
            continue
        lit = _vector_text_literal(arr)
        res = db.execute(
            text(
                """
                UPDATE papers SET embedding_vec = CAST(:v AS vector)
                WHERE id = :id AND embedding_vec IS NULL
                """
            ),
            {"v": lit, "id": int(pid)},
        )
        updated += res.rowcount or 0
    if updated:
        db.commit()
        logger.info("pgvector backfill: wrote embedding_vec for %s papers", updated)
    return updated
