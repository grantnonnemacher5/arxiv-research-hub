"""One-shot: copy `papers.embedding` blobs into `embedding_vec` for pgvector ANN search.

Run on PostgreSQL after deploy:  python backfill_pgvector.py
(from the backend/ directory, with DATABASE_URL set)
"""

from __future__ import annotations

import sys

from sqlalchemy import func, select, text

from database import Paper, SessionLocal, engine, init_db
from pgvector_support import backfill_embedding_vec_from_blobs, count_pgvector_indexed, is_postgres_engine


def main() -> None:
    init_db()
    if not is_postgres_engine(engine):
        print(
            "backfill_pgvector: DATABASE_URL must be PostgreSQL (e.g. Neon). "
            "SQLite has no embedding_vec column; skip.",
            file=sys.stderr,
        )
        sys.exit(0)

    db = SessionLocal()
    try:
        n_papers = db.scalar(select(func.count()).select_from(Paper)) or 0
        n_emb = db.scalar(select(func.count()).select_from(Paper).where(Paper.embedding.isnot(None))) or 0
        n_vec = count_pgvector_indexed(db)
        try:
            n_pending = db.scalar(
                text(
                    "SELECT COUNT(*) FROM papers WHERE embedding IS NOT NULL AND embedding_vec IS NULL"
                )
            )
        except Exception:
            n_pending = None
        print(
            f"backfill_pgvector: papers={n_papers} with_embedding_blob={n_emb} with_embedding_vec={n_vec} "
            f"pending_backfill={n_pending}",
            file=sys.stderr,
        )

        total = 0
        while True:
            n = backfill_embedding_vec_from_blobs(db, batch_limit=500)
            total += n
            if n == 0:
                break
        print(f"backfill_pgvector: updated {total} rows total", file=sys.stderr)
        if total == 0 and n_pending:
            print(
                "backfill_pgvector: pending rows exist but 0 updates — check OPENAI_EMBED_DIMENSION "
                "matches embedding blob length (e.g. 1536 for text-embedding-3-small).",
                file=sys.stderr,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
