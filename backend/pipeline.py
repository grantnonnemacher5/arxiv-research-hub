"""Full ingest + classify pipeline (plan Day 2 scheduler + manual run)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from arxiv_ingestion import fetch_all_bucket_queries
from classifier import (
    buckets_to_csv,
    classify_paper_text,
    paper_text_for_embedding,
)
from config import OPENAI_API_KEY
from database import Paper, SessionLocal, init_db, strip_nul_bytes
from deduplicator import is_duplicate
from pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)


def _classify_and_pack(text: str) -> tuple[str, bytes | None]:
    if not OPENAI_API_KEY or not text.strip():
        return "", None
    try:
        labels, emb = classify_paper_text(text)
        return buckets_to_csv(labels), emb if emb else None
    except Exception:
        logger.exception("Classification failed; storing paper without buckets")
        return "", None


def backfill_classifications(db: Session) -> int:
    """Fill buckets/embedding for rows missing them (e.g. Day 1 ingest)."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set; skipping classification backfill")
        return 0
    stmt = select(Paper).where(or_(Paper.embedding.is_(None), Paper.buckets == ""))
    rows = list(db.scalars(stmt).all())
    updated = 0
    for row in rows:
        text = paper_text_for_embedding(row.full_text, row.abstract)
        if not text:
            continue
        buckets, emb = classify_paper_text(text)
        row.buckets = strip_nul_bytes(buckets_to_csv(buckets)) or ""
        row.embedding = emb if emb else None
        updated += 1
    if updated:
        db.commit()
    logger.info("Backfill classification updated %s rows", updated)
    return updated


def run_full_pipeline(max_results_per_query: int | None = None) -> dict[str, Any]:
    """
    1) Fetch arXiv 2) dedupe 3) PDF text 4) classify 5) save.
    Then backfill classification for older rows missing labels.
    """
    init_db()
    db = SessionLocal()
    saved = 0
    skipped = 0
    try:
        papers = fetch_all_bucket_queries(max_results_per_query=max_results_per_query)
        logger.info("Pipeline fetched %s candidate papers", len(papers))
        for p in papers:
            if is_duplicate(p["arxiv_id"], db):
                skipped += 1
                continue
            pdf_url = p.get("pdf_url") or ""
            full_text = extract_text_from_pdf(pdf_url) if pdf_url else None
            full_text = strip_nul_bytes(full_text)
            text = paper_text_for_embedding(full_text, p.get("abstract") or "")
            bucket_str, emb = _classify_and_pack(text)
            row = Paper(
                arxiv_id=strip_nul_bytes(p["arxiv_id"]) or "",
                title=strip_nul_bytes(p["title"]) or "",
                authors=strip_nul_bytes(p["authors"]) or "",
                abstract=strip_nul_bytes(p.get("abstract") or "") or "",
                full_text=full_text,
                pdf_url=strip_nul_bytes(pdf_url) or "",
                published_date=p.get("published_date"),
                buckets=strip_nul_bytes(bucket_str) or "",
                embedding=emb,
            )
            db.add(row)
            db.commit()
            saved += 1
            logger.info("Ingested %s — %s", p["arxiv_id"], (p.get("title") or "")[:80])

        backfilled = backfill_classifications(db)
        return {"saved": saved, "skipped_duplicates": skipped, "backfilled": backfilled}
    finally:
        db.close()
