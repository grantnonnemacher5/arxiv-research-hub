"""Fill `buckets` (+ OpenAI `embedding` when a key is set), then copy blobs → `embedding_vec` on Postgres.

Without OPENAI_API_KEY, buckets use **keyword heuristics** (see `classifier.classify_paper_text_keyword`); no
embedding blobs or API calls. With a key, embeddings match the normal ingest path.

Usage (from `backend/`):

  python3 backfill_classifications.py
  python3 backfill_classifications.py --pgvector-only   # blob → embedding_vec only (Postgres)

Then if needed:

  python3 backfill_pgvector.py
"""

from __future__ import annotations

import argparse
import sys

from config import OPENAI_API_KEY
from database import SessionLocal, engine, init_db
from pgvector_support import backfill_embedding_vec_from_blobs, is_postgres_engine
from pipeline import backfill_classifications


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill bucket labels (+ embeddings when OpenAI is set).")
    parser.add_argument(
        "--pgvector-only",
        action="store_true",
        help="Only copy embedding blobs → embedding_vec (Postgres). No classification.",
    )
    args = parser.parse_args()

    if args.pgvector_only:
        init_db()
        if not is_postgres_engine(engine):
            print("backfill_classifications: --pgvector-only needs PostgreSQL.", file=sys.stderr)
            sys.exit(1)
        db = SessionLocal()
        try:
            total = 0
            while True:
                n = backfill_embedding_vec_from_blobs(db, batch_limit=500)
                total += n
                if n == 0:
                    break
            print(f"pgvector-only: updated {total} embedding_vec rows", file=sys.stderr)
        finally:
            db.close()
        return

    init_db()
    db = SessionLocal()
    try:
        mode = "OpenAI embeddings" if OPENAI_API_KEY else "keyword-only (no API)"
        print(f"backfill_classifications: mode={mode}", file=sys.stderr)
        n = backfill_classifications(db)
        print(f"classification backfill: updated {n} papers", file=sys.stderr)

        if is_postgres_engine(engine):
            total = 0
            while True:
                k = backfill_embedding_vec_from_blobs(db, batch_limit=500)
                total += k
                if k == 0:
                    break
            print(f"pgvector sync: updated {total} embedding_vec rows", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
