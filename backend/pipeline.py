"""Full ingest + classify pipeline (plan Day 2 scheduler + manual run)."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from arxiv_ingestion import fetch_all_bucket_queries
from classifier import (
    buckets_to_csv,
    classify_paper_text,
    classification_input_text,
)
from config import OPENAI_API_KEY
from database import Paper, PipelineRun, SessionLocal, init_db, strip_nul_bytes
from deduplicator import is_duplicate
from pdf_extractor import extract_text_from_pdf
from pgvector_support import sync_paper_embedding_vec
from webhook_notify import send_pipeline_webhook

logger = logging.getLogger(__name__)


def _record_pipeline_run(
    *,
    started_at: datetime,
    trigger: Literal["manual", "scheduled"],
    status: Literal["completed", "failed"],
    duration_ms: int,
    saved: int,
    skipped: int,
    backfilled: int,
    error: str | None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            PipelineRun(
                started_at=started_at,
                finished_at=datetime.utcnow(),
                trigger=trigger,
                status=status,
                saved=saved,
                skipped_duplicates=skipped,
                backfilled=backfilled,
                duration_ms=max(0, duration_ms),
                error=error,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to record pipeline run")
    finally:
        db.close()


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
        text = classification_input_text(row.full_text, row.abstract)
        if not text:
            continue
        buckets, emb = classify_paper_text(text)
        row.buckets = strip_nul_bytes(buckets_to_csv(buckets)) or ""
        row.embedding = emb if emb else None
        db.flush()
        if emb:
            sync_paper_embedding_vec(db, row.id, emb)
        updated += 1
    if updated:
        db.commit()
    logger.info("Backfill classification updated %s rows", updated)
    return updated


def run_full_pipeline(
    max_results_per_query: int | None = None,
    trigger: Literal["manual", "scheduled"] = "manual",
) -> dict[str, Any]:
    """
    1) Fetch arXiv 2) dedupe 3) PDF text 4) classify 5) save.
    Then backfill classification for older rows missing labels.
    On completion or failure, POST to WEBHOOK_URL when configured.
    Records a PipelineRun row for ops metrics.
    """
    init_db()
    started_at = datetime.utcnow()
    t0 = time.monotonic()
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
            text = classification_input_text(full_text, p.get("abstract") or "")
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
            db.flush()
            if emb:
                sync_paper_embedding_vec(db, row.id, emb)
            db.commit()
            saved += 1
            logger.info("Ingested %s — %s", p["arxiv_id"], (p.get("title") or "")[:80])

        backfilled = backfill_classifications(db)
        stats: dict[str, Any] = {
            "saved": saved,
            "skipped_duplicates": skipped,
            "backfilled": backfilled,
        }
        duration_ms = int((time.monotonic() - t0) * 1000)
        send_pipeline_webhook("completed", stats, None, t0)
        _record_pipeline_run(
            started_at=started_at,
            trigger=trigger,
            status="completed",
            duration_ms=duration_ms,
            saved=saved,
            skipped=skipped,
            backfilled=backfilled,
            error=None,
        )
        return stats
    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        send_pipeline_webhook("failed", None, str(e)[:4000], t0)
        _record_pipeline_run(
            started_at=started_at,
            trigger=trigger,
            status="failed",
            duration_ms=duration_ms,
            saved=saved,
            skipped=skipped,
            backfilled=0,
            error=str(e)[:8000],
        )
        raise
    finally:
        db.close()
