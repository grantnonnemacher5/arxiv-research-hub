"""Full ingest + classify pipeline (plan Day 2 scheduler + manual run)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from arxiv_ingestion import fetch_all_bucket_queries
from config import (
    ARXIV_SYNC_MAX_OFFSET_BLOCKS,
    ARXIV_SYNC_MAX_SAVES_PER_RUN,
    ARXIV_SYNC_STOP_ALL_DUP_STREAK,
    BACKFILL_CLASSIFICATION_BATCH_SIZE,
    INGEST_FETCH_PDF,
    OPENAI_API_KEY,
)
from classifier import (
    buckets_to_csv,
    classify_paper_text,
    classification_input_text,
)
from database import Paper, PipelineRun, SessionLocal, init_db, strip_nul_bytes
from deduplicator import is_duplicate
from pdf_extractor import extract_text_from_pdf
from pgvector_support import sync_paper_embedding_vec
from webhook_notify import send_pipeline_webhook

logger = logging.getLogger(__name__)

_pipeline_lock = threading.Lock()


def pipeline_is_busy() -> bool:
    """True while any thread is inside ``run_full_pipeline``."""
    return _pipeline_lock.locked()


def _create_pipeline_run_started(
    trigger: Literal["manual", "scheduled"],
    started_at: datetime,
) -> int | None:
    """Insert a ``running`` row so deploy/OOM mid-sync still leaves a visible audit row."""
    db = SessionLocal()
    try:
        row = PipelineRun(
            started_at=started_at,
            finished_at=started_at,
            trigger=trigger,
            status="running",
            saved=0,
            skipped_duplicates=0,
            backfilled=0,
            duration_ms=0,
            error=None,
        )
        db.add(row)
        db.commit()
        return int(row.id)
    except Exception:
        logger.exception("Failed to create started pipeline run")
        return None
    finally:
        db.close()


def _finalize_pipeline_run(
    run_id: int | None,
    *,
    status: Literal["completed", "failed"],
    duration_ms: int,
    saved: int,
    skipped: int,
    backfilled: int,
    error: str | None,
) -> None:
    if run_id is None:
        return
    db = SessionLocal()
    try:
        row = db.get(PipelineRun, run_id)
        if row is None:
            return
        row.finished_at = datetime.utcnow()
        row.status = status
        row.saved = saved
        row.skipped_duplicates = skipped
        row.backfilled = backfilled
        row.duration_ms = max(0, duration_ms)
        row.error = error
        db.commit()
    except Exception:
        logger.exception("Failed to finalize pipeline run id=%s", run_id)
    finally:
        db.close()


def _update_pipeline_run_progress(run_id: int | None, saved: int, skipped: int, t0: float) -> None:
    """Update ``running`` row with partial saved/skipped (UI + ops during long syncs)."""
    if run_id is None:
        return
    db = SessionLocal()
    try:
        row = db.get(PipelineRun, run_id)
        if row is None or row.status != "running":
            return
        row.saved = saved
        row.skipped_duplicates = skipped
        row.duration_ms = max(0, int((time.monotonic() - t0) * 1000))
        db.commit()
    except Exception:
        logger.debug("Pipeline run progress update failed", exc_info=True)
        db.rollback()
    finally:
        db.close()


def close_stale_running_pipeline_runs() -> int:
    """Mark ``running`` rows failed after OOM/deploy/SIGKILL (never finalized)."""
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(PipelineRun).where(PipelineRun.status == "running")).all())
        if not rows:
            return 0
        now = datetime.utcnow()
        n = 0
        for row in rows:
            row.status = "failed"
            row.finished_at = now
            row.error = (
                "Interrupted before completion (deploy, instance restart, or out of memory). "
                "Partial saved/skipped may reflect progress before shutdown."
            )
            started = row.started_at
            if getattr(started, "tzinfo", None) is not None:
                started = started.replace(tzinfo=None)
            row.duration_ms = max(0, int((now - started).total_seconds() * 1000))
            n += 1
        db.commit()
        return n
    except Exception:
        logger.exception("close_stale_running_pipeline_runs failed")
        db.rollback()
        return 0
    finally:
        db.close()


def _classify_and_pack(text: str) -> tuple[str, bytes | None]:
    if not text.strip():
        return "", None
    try:
        labels, emb = classify_paper_text(text)
        return buckets_to_csv(labels), emb if emb else None
    except Exception:
        logger.exception("Classification failed; storing paper without buckets")
        return "", None


def backfill_classifications(db: Session) -> int:
    """Fill buckets/embedding for rows missing them (keyword-only when no OpenAI key).

    Keyword mode never persists embeddings (``embedding`` stays NULL). Selecting
    ``embedding IS NULL`` would therefore match the entire library and load every
    ``full_text`` at once — enough to OOM small instances (e.g. Render 512MB).

    Uses keyset batches (ordered by id) so we never load the full table and we
    always advance past a batch even when some rows have no classifiable text.
    """
    if OPENAI_API_KEY:
        filter_cond = or_(Paper.embedding.is_(None), Paper.buckets == "")
    else:
        filter_cond = Paper.buckets == ""

    updated = 0
    batch_size = BACKFILL_CLASSIFICATION_BATCH_SIZE
    cursor_id = 0
    while True:
        rows = list(
            db.scalars(
                select(Paper)
                .where(filter_cond, Paper.id > cursor_id)
                .order_by(Paper.id)
                .limit(batch_size)
            ).all()
        )
        if not rows:
            break
        cursor_id = rows[-1].id
        batch_updates = 0
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
            batch_updates += 1
        if batch_updates:
            db.commit()
        # Release ORM identity map between batches (important on low-RAM hosts).
        db.expunge_all()
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
    with _pipeline_lock:
        return _run_full_pipeline_impl(max_results_per_query, trigger)


def _run_full_pipeline_impl(
    max_results_per_query: int | None = None,
    trigger: Literal["manual", "scheduled"] = "manual",
) -> dict[str, Any]:
    init_db()
    if not INGEST_FETCH_PDF:
        logger.info("INGEST_FETCH_PDF=false — skipping PDF downloads during ingest (abstract/metadata only)")
    started_at = datetime.utcnow()
    t0 = time.monotonic()
    run_id = _create_pipeline_run_started(trigger, started_at)
    db = SessionLocal()
    saved = 0
    skipped = 0
    progress_counter = 0

    def bump_progress_checkpoint() -> None:
        nonlocal progress_counter
        progress_counter += 1
        if run_id and progress_counter % 5 == 0:
            _update_pipeline_run_progress(run_id, saved, skipped, t0)

    try:
        all_dup_streak = 0
        save_cap_reached = False
        for start_block in range(ARXIV_SYNC_MAX_OFFSET_BLOCKS):
            if start_block > 0:
                time.sleep(3.1)
            papers = fetch_all_bucket_queries(
                max_results_per_query=max_results_per_query,
                start_block=start_block,
            )
            logger.info(
                "Pipeline arXiv offset block %s: %s candidate papers",
                start_block,
                len(papers),
            )
            if not papers:
                logger.info("Pipeline: no arXiv candidates at offset block %s; stopping", start_block)
                break
            block_new = 0
            for p in papers:
                if is_duplicate(p["arxiv_id"], db):
                    skipped += 1
                    bump_progress_checkpoint()
                    continue
                pdf_url = p.get("pdf_url") or ""
                if INGEST_FETCH_PDF and pdf_url:
                    full_text = extract_text_from_pdf(pdf_url)
                else:
                    full_text = None
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
                try:
                    db.add(row)
                    db.flush()
                    if emb:
                        sync_paper_embedding_vec(db, row.id, emb)
                    db.commit()
                except IntegrityError:
                    # Another sync (or retry) inserted the same arxiv_id after our duplicate check.
                    db.rollback()
                    skipped += 1
                    logger.warning(
                        "Skip %s after IntegrityError (concurrent insert or duplicate)",
                        p.get("arxiv_id"),
                    )
                    bump_progress_checkpoint()
                    continue
                saved += 1
                block_new += 1
                bump_progress_checkpoint()
                logger.info("Ingested %s — %s", p["arxiv_id"], (p.get("title") or "")[:80])
                if saved >= ARXIV_SYNC_MAX_SAVES_PER_RUN:
                    save_cap_reached = True
                    logger.info(
                        "Pipeline: reached ARXIV_SYNC_MAX_SAVES_PER_RUN=%s — stopping ingest "
                        "(saved=%s, skipped=%s).",
                        ARXIV_SYNC_MAX_SAVES_PER_RUN,
                        saved,
                        skipped,
                    )
                    break
            if save_cap_reached:
                break
            if block_new > 0:
                all_dup_streak = 0
            else:
                all_dup_streak += 1
                if all_dup_streak >= ARXIV_SYNC_STOP_ALL_DUP_STREAK:
                    logger.info(
                        "Pipeline: stopping after %s consecutive blocks with no new saves",
                        all_dup_streak,
                    )
                    break

        if run_id:
            _update_pipeline_run_progress(run_id, saved, skipped, t0)
        backfilled = backfill_classifications(db)
        stats: dict[str, Any] = {
            "saved": saved,
            "skipped_duplicates": skipped,
            "backfilled": backfilled,
        }
        duration_ms = int((time.monotonic() - t0) * 1000)
        send_pipeline_webhook("completed", stats, None, t0)
        _finalize_pipeline_run(
            run_id,
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
        _finalize_pipeline_run(
            run_id,
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
