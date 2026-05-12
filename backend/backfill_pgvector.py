"""One-shot: copy `papers.embedding` blobs into `embedding_vec` for pgvector ANN search.

Run on PostgreSQL after deploy:  python backfill_pgvector.py
(from the backend/ directory, with DATABASE_URL set)
"""

from __future__ import annotations

import sys

from database import SessionLocal, init_db
from pgvector_support import backfill_embedding_vec_from_blobs


def main() -> None:
    init_db()
    db = SessionLocal()
    total = 0
    try:
        while True:
            n = backfill_embedding_vec_from_blobs(db, batch_limit=500)
            total += n
            if n == 0:
                break
        print(f"backfill_pgvector: updated {total} rows total", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    main()
