"""
Day 1 manual test: fetch arXiv → dedupe → PDF text → save to SQLite.
Run from repo root:  python backend/ingest_once.py
Or from backend:     python ingest_once.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Allow `python backend/ingest_once.py` (cwd = repo root)
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.chdir(_BACKEND)

from arxiv_ingestion import fetch_all_bucket_queries  # noqa: E402
from database import Paper, SessionLocal, init_db  # noqa: E402
from deduplicator import is_duplicate  # noqa: E402
from pdf_extractor import extract_text_from_pdf  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_once")


def run_ingestion(max_results_per_query: int | None = None) -> tuple[int, int]:
    init_db()
    db = SessionLocal()
    saved = 0
    skipped = 0
    try:
        papers = fetch_all_bucket_queries(max_results_per_query=max_results_per_query)
        logger.info("Fetched %s unique paper entries from arXiv", len(papers))
        for p in papers:
            if is_duplicate(p["arxiv_id"], db):
                skipped += 1
                continue
            pdf_url = p.get("pdf_url") or ""
            full_text = extract_text_from_pdf(pdf_url) if pdf_url else None
            row = Paper(
                arxiv_id=p["arxiv_id"],
                title=p["title"],
                authors=p["authors"],
                abstract=p["abstract"],
                full_text=full_text,
                pdf_url=pdf_url,
                published_date=p.get("published_date"),
                buckets="",
                embedding=None,
            )
            db.add(row)
            db.commit()
            saved += 1
            logger.info("Saved %s — %s", p["arxiv_id"], p["title"][:80])
    finally:
        db.close()
    return saved, skipped


def main() -> None:
    # Smaller default for a quick first run unless overridden
    per_q = int(os.environ.get("DAY1_MAX_PER_QUERY", "5"))
    saved, skipped = run_ingestion(max_results_per_query=per_q)
    logger.info("Done. saved=%s skipped_duplicates=%s", saved, skipped)


if __name__ == "__main__":
    main()
