"""Full ingest + classify pipeline (plan Day 2 scheduler + manual run)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Literal

import requests
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from arxiv_ingestion import (
    build_dated_search_query,
    fetch_all_bucket_queries,
    fetch_arxiv_papers,
    jittered_delay,
)
from ingest_checkpoint import get_next_deep_block, save_next_deep_block
from ingest_watermark import (
    bump_consecutive_429s,
    load_watermarks,
    reset_consecutive_429s,
    update_watermark,
)
from config import (
    ARXIV_BOOTSTRAP_WINDOW_DAYS,
    ARXIV_CATEGORY_429_BREAKER,
    ARXIV_FRESH_MAX_PAGES_PER_CATEGORY,
    ARXIV_MAX_RESULTS,
    ARXIV_QUERIES,
    ARXIV_REQUEST_DELAY_SEC,
    ARXIV_RESUME_DEEP_SCAN,
    ARXIV_RUN_DEEP_BACKFILL,
    ARXIV_SAFETY_OVERLAP_HOURS,
    ARXIV_SYNC_MAX_OFFSET_BLOCKS,
    ARXIV_SYNC_MAX_SAVES_PER_RUN,
    ARXIV_SYNC_STOP_ALL_DUP_STREAK,
    ARXIV_USE_WATERMARK_FRESH,
    BACKFILL_CLASSIFICATION_BATCH_SIZE,
    INGEST_DEMO_DEEP_START_BLOCK,
    INGEST_DEMO_MODE,
    INGEST_DEMO_SKIP_FRESH,
    INGEST_FETCH_PDF,
    INGEST_TIME_BUDGET_SEC,
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
_pipeline_cancel = threading.Event()


def _interruptible_sleep(seconds: float) -> None:
    """Sleep up to ``seconds`` but wake immediately when cancel is requested."""
    if seconds <= 0:
        return
    # Event.wait returns True if the event got set during the wait; we ignore
    # the return value since callers already inspect ``pipeline_cancel_requested``.
    _pipeline_cancel.wait(timeout=seconds)


def pipeline_is_busy() -> bool:
    """True while any thread is inside ``run_full_pipeline``."""
    return _pipeline_lock.locked()


def pipeline_cancel_requested() -> bool:
    return _pipeline_cancel.is_set()


def request_pipeline_cancel() -> None:
    """Ask the in-process pipeline to stop between papers / offset blocks (cooperative)."""
    _pipeline_cancel.set()


def clear_pipeline_cancel() -> None:
    _pipeline_cancel.clear()


def create_pipeline_run_started(
    trigger: Literal["manual", "scheduled"],
    started_at: datetime | None = None,
) -> int | None:
    """Insert a ``running`` row up-front. Public wrapper so the HTTP handler can
    pre-create the row before launching the worker thread, ensuring the UI
    shows the new run on its first poll instead of after a thread-start delay.
    """
    return _create_pipeline_run_started(trigger, started_at or datetime.utcnow())


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
    status: Literal["completed", "failed", "cancelled"],
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


def _empty_ingest_note(
    *,
    saved: int,
    skipped: int,
    saw_candidates: bool,
    fetch_meta: dict[str, Any],
    time_budget_exhausted: bool = False,
) -> str | None:
    """Human-readable note when a run completes (returned only when something is worth saying)."""
    breaker_cats = fetch_meta.get("categories_breaker_tripped") or []
    if saved > 0 or skipped > 0:
        notes: list[str] = []
        if time_budget_exhausted:
            notes.append(
                f"Time budget reached ({INGEST_TIME_BUDGET_SEC}s) — remaining work continues on next run."
            )
        if breaker_cats:
            notes.append(
                f"arXiv rate-limited categories: {', '.join(breaker_cats)} (other categories ingested OK)."
            )
        return " ".join(notes) if notes else None
    failed = int(fetch_meta.get("requests_failed") or 0)
    ok = int(fetch_meta.get("requests_ok") or 0)
    last_err = (fetch_meta.get("last_error") or "").strip()
    if failed > 0 and ok == 0:
        if "429" in last_err or "Too Many Requests" in last_err:
            return (
                "arXiv rate-limited this sync (HTTP 429). Wait a few minutes and run again; "
                "the API retries automatically with backoff."
            )
        base = f"Could not reach arXiv API ({failed} failed request(s))."
        if last_err:
            return f"{base} Last error: {last_err[:220]}"
        return f"{base} Check Hugging Face Space logs for 'arXiv fetch failed'."
    if not saw_candidates:
        return "arXiv returned no papers for this sync (empty feed or all categories failed)."
    return (
        "No new papers saved; every candidate was already in the library or had no classifiable text."
    )


def _classify_and_pack(text: str) -> tuple[str, bytes | None]:
    if not text.strip():
        return "", None
    try:
        labels, emb = classify_paper_text(text)
        return buckets_to_csv(labels), emb if emb else None
    except Exception:
        logger.exception("Classification failed; storing paper without buckets")
        return "", None


# ----------------------------------------------------------------------------
# Ingest v2: watermark-driven fresh pass (see plan.md "Ingest pipeline v2").
# ----------------------------------------------------------------------------

def _extract_category_key(category_query: str) -> str:
    """``cat:cs.AI`` -> ``cs.AI``. Falls back to the raw query if no prefix."""
    raw = category_query.strip()
    if raw.lower().startswith("cat:"):
        return raw[4:]
    return raw


def _save_paper(
    db: Session,
    p: dict[str, Any],
) -> tuple[bool, bool]:
    """Run the existing classify + persist path for one paper candidate.

    Returns ``(saved, conflicted)``. ``conflicted`` is True when an IntegrityError
    suggests another writer inserted the same arxiv_id concurrently — caller treats
    as a skip, not a save.
    """
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
        return True, False
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Skip %s after IntegrityError (concurrent insert or duplicate)",
            p.get("arxiv_id"),
        )
        return False, True


def _run_fresh_pass(
    db: Session,
    *,
    t0: float,
    run_id: int | None,
    bump_progress: Any,
) -> dict[str, Any]:
    """Per-category date-windowed scan honoring watermarks + time budget + 429 breaker.

    Returns a dict with cumulative ``saved`` / ``skipped`` and flags consumed by the
    finalizer (``cancelled``, ``save_cap_reached``, ``time_budget_exhausted``,
    ``saw_any_candidates``, ``fetch_meta``).
    """
    saved = 0
    skipped = 0
    saw_any = False
    cancelled = False
    save_cap_reached = False
    time_budget_exhausted = False
    fetch_meta: dict[str, Any] = {
        "requests_ok": 0,
        "requests_failed": 0,
        "last_error": None,
        "categories_breaker_tripped": [],
    }
    seen_in_run: set[str] = set()

    raw_categories = list(ARXIV_QUERIES)
    cat_keys = [_extract_category_key(c) for c in raw_categories]
    watermarks = load_watermarks(cat_keys)
    bootstrap_floor = (datetime.utcnow() - timedelta(days=ARXIV_BOOTSTRAP_WINDOW_DAYS)).date()
    logger.info(
        "Fresh pass watermarks (bootstrap floor=%s, overlap=%sh, budget=%ss): %s",
        bootstrap_floor.isoformat(),
        ARXIV_SAFETY_OVERLAP_HOURS,
        INGEST_TIME_BUDGET_SEC,
        {k: (v.isoformat() if v else None) for k, v in watermarks.items()},
    )

    def time_left() -> float:
        return INGEST_TIME_BUDGET_SEC - (time.monotonic() - t0)

    for cat_query, cat_key in zip(raw_categories, cat_keys):
        if pipeline_cancel_requested():
            cancelled = True
            break
        if time_left() <= 0:
            time_budget_exhausted = True
            logger.info(
                "Fresh pass: time budget exhausted before category %s — stopping cleanly",
                cat_key,
            )
            break

        wm = watermarks.get(cat_key)
        start_date = wm or bootstrap_floor
        from_dt = datetime.combine(start_date, datetime.min.time()) - timedelta(
            hours=ARXIV_SAFETY_OVERLAP_HOURS
        )
        query = build_dated_search_query(cat_query, from_dt)
        logger.info(
            "Fresh pass [%s]: window from %s (watermark=%s)",
            cat_key,
            from_dt.isoformat(timespec="minutes"),
            wm.isoformat() if wm else "none",
        )

        max_seen_date: date | None = None
        cat_429s = 0
        cat_breaker_tripped = False

        for page_i in range(ARXIV_FRESH_MAX_PAGES_PER_CATEGORY):
            if pipeline_cancel_requested():
                cancelled = True
                break
            if time_left() <= 0:
                time_budget_exhausted = True
                logger.info(
                    "Fresh pass [%s]: time budget exhausted at page %s",
                    cat_key,
                    page_i,
                )
                break
            if page_i > 0 or fetch_meta["requests_ok"] + fetch_meta["requests_failed"] > 0:
                _interruptible_sleep(jittered_delay())
                if pipeline_cancel_requested():
                    cancelled = True
                    break
                if time_left() <= 0:
                    time_budget_exhausted = True
                    break

            try:
                batch = fetch_arxiv_papers(
                    query,
                    max_results=ARXIV_MAX_RESULTS,
                    start=page_i * ARXIV_MAX_RESULTS,
                    cancel_check=pipeline_cancel_requested,
                    interruptible_sleep=_interruptible_sleep,
                )
                fetch_meta["requests_ok"] += 1
                reset_consecutive_429s(cat_key)
            except requests.HTTPError as exc:
                fetch_meta["requests_failed"] += 1
                fetch_meta["last_error"] = str(exc)[:500]
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code == 429:
                    cat_429s += 1
                    bump_consecutive_429s(cat_key)
                    if cat_429s >= ARXIV_CATEGORY_429_BREAKER:
                        cat_breaker_tripped = True
                        fetch_meta["categories_breaker_tripped"].append(cat_key)
                        logger.warning(
                            "Fresh pass [%s]: circuit breaker tripped after %s 429s — skipping remaining pages",
                            cat_key,
                            cat_429s,
                        )
                        break
                    logger.warning(
                        "Fresh pass [%s]: 429 on page %s (%s/%s before breaker)",
                        cat_key,
                        page_i,
                        cat_429s,
                        ARXIV_CATEGORY_429_BREAKER,
                    )
                    continue
                logger.error("Fresh pass [%s]: HTTP error %s", cat_key, exc)
                break
            except Exception as exc:
                fetch_meta["requests_failed"] += 1
                fetch_meta["last_error"] = str(exc)[:500]
                logger.error("Fresh pass [%s]: fetch failed: %s", cat_key, exc)
                break

            if not batch:
                logger.info(
                    "Fresh pass [%s]: empty page %s — window exhausted",
                    cat_key,
                    page_i,
                )
                break

            saw_any = True
            page_new = 0
            for p in batch:
                if pipeline_cancel_requested():
                    cancelled = True
                    break
                aid = p.get("arxiv_id")
                if not aid or aid in seen_in_run:
                    continue
                seen_in_run.add(aid)
                pub_date = p.get("published_date")
                if pub_date and (max_seen_date is None or pub_date > max_seen_date):
                    max_seen_date = pub_date
                if is_duplicate(aid, db):
                    skipped += 1
                    bump_progress()
                    continue
                did_save, conflicted = _save_paper(db, p)
                if conflicted:
                    skipped += 1
                    bump_progress()
                    continue
                if did_save:
                    saved += 1
                    page_new += 1
                    bump_progress()
                    logger.info("Ingested %s — %s", aid, (p.get("title") or "")[:80])
                    if saved >= ARXIV_SYNC_MAX_SAVES_PER_RUN:
                        save_cap_reached = True
                        logger.info(
                            "Fresh pass: reached ARXIV_SYNC_MAX_SAVES_PER_RUN=%s — stopping (saved=%s skipped=%s).",
                            ARXIV_SYNC_MAX_SAVES_PER_RUN,
                            saved,
                            skipped,
                        )
                        break

            if cancelled or save_cap_reached:
                break
            if page_new == 0:
                # arXiv sorts DESC by submittedDate: an all-dup page means older pages are also dups.
                logger.info(
                    "Fresh pass [%s]: page %s had 0 new — stopping pagination for this category",
                    cat_key,
                    page_i,
                )
                break

        if max_seen_date is not None and not cat_breaker_tripped:
            update_watermark(cat_key, max_seen_date, run_id=run_id)

        if cancelled or save_cap_reached:
            break

    return {
        "saved": saved,
        "skipped": skipped,
        "cancelled": cancelled,
        "save_cap_reached": save_cap_reached,
        "time_budget_exhausted": time_budget_exhausted,
        "saw_any_candidates": saw_any,
        "fetch_meta": fetch_meta,
    }


def backfill_classifications(db: Session) -> int:
    """Fill buckets/embedding for rows missing them (keyword-only when no OpenAI key).

    Keyword mode never persists embeddings (``embedding`` stays NULL). Selecting
    ``embedding IS NULL`` would therefore match the entire library and load every
    ``full_text`` at once — enough to OOM small instances (e.g. Render 512MB).

    Uses keyset batches (ordered by id) so we never load the full table and we
    always advance past a batch even when some rows have no classifiable text.

    Honours ``pipeline_cancel_requested()`` between batches and between rows so
    Stop sync takes effect quickly even when backfill is the active phase.
    """
    if OPENAI_API_KEY:
        filter_cond = or_(Paper.embedding.is_(None), Paper.buckets == "")
    else:
        filter_cond = Paper.buckets == ""

    updated = 0
    batch_size = BACKFILL_CLASSIFICATION_BATCH_SIZE
    cursor_id = 0
    while True:
        if pipeline_cancel_requested():
            logger.info(
                "Backfill: cancel requested before next batch — exiting (updated=%s)",
                updated,
            )
            break
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
        cancelled_in_batch = False
        for row in rows:
            if pipeline_cancel_requested():
                logger.info(
                    "Backfill: cancel requested mid-batch — exiting (updated=%s)",
                    updated,
                )
                cancelled_in_batch = True
                break
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
        if cancelled_in_batch:
            break
    logger.info("Backfill classification updated %s rows", updated)
    return updated


def run_full_pipeline(
    max_results_per_query: int | None = None,
    trigger: Literal["manual", "scheduled"] = "manual",
    run_id: int | None = None,
) -> dict[str, Any]:
    """
    1) Fetch arXiv 2) dedupe 3) PDF text 4) classify 5) save.
    Then backfill classification for older rows missing labels.
    On completion or failure, POST to WEBHOOK_URL when configured.
    Records a PipelineRun row for ops metrics.

    ``run_id`` lets the HTTP handler pre-create the ``running`` row synchronously
    so the dashboard sees it on the next poll. When None, a row is created here
    (still the path used by the scheduler).
    """
    with _pipeline_lock:
        return _run_full_pipeline_impl(max_results_per_query, trigger, run_id)


def _run_full_pipeline_impl(
    max_results_per_query: int | None = None,
    trigger: Literal["manual", "scheduled"] = "manual",
    run_id: int | None = None,
) -> dict[str, Any]:
    init_db()
    clear_pipeline_cancel()
    if not INGEST_FETCH_PDF:
        logger.info("INGEST_FETCH_PDF=false — skipping PDF downloads during ingest (abstract/metadata only)")
    started_at = datetime.utcnow()
    t0 = time.monotonic()
    if run_id is None:
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

    fetch_meta: dict[str, Any] = {"requests_ok": 0, "requests_failed": 0, "last_error": None}
    saw_any_candidates = False

    try:
        all_dup_streak = 0
        save_cap_reached = False
        cancelled_early = False
        time_budget_exhausted = False

        if ARXIV_USE_WATERMARK_FRESH and not INGEST_DEMO_SKIP_FRESH:
            fresh_result = _run_fresh_pass(
                db,
                t0=t0,
                run_id=run_id,
                bump_progress=bump_progress_checkpoint,
            )
            saved += fresh_result["saved"]
            skipped += fresh_result["skipped"]
            fetch_meta = fresh_result["fetch_meta"]
            saw_any_candidates = fresh_result["saw_any_candidates"] or saw_any_candidates
            cancelled_early = fresh_result["cancelled"]
            save_cap_reached = fresh_result["save_cap_reached"]
            time_budget_exhausted = fresh_result["time_budget_exhausted"]
            logger.info(
                "Fresh pass complete: saved=%s skipped=%s cancelled=%s save_cap=%s time_budget=%s",
                fresh_result["saved"],
                fresh_result["skipped"],
                cancelled_early,
                save_cap_reached,
                time_budget_exhausted,
            )
        elif ARXIV_USE_WATERMARK_FRESH and INGEST_DEMO_SKIP_FRESH:
            logger.info(
                "Fresh pass skipped (INGEST_DEMO_SKIP_FRESH) — deep backfill only for demo ingest"
            )

        # Legacy deep offset-block backfill — runs only when explicitly enabled
        # (e.g. a weekly schedule or one-off catch-up). Default daily run uses the
        # fresh pass above and skips this block entirely.
        run_deep_backfill = (
            not ARXIV_USE_WATERMARK_FRESH or ARXIV_RUN_DEEP_BACKFILL
        ) and not cancelled_early and not save_cap_reached and not time_budget_exhausted

        if INGEST_DEMO_MODE:
            deep_start = INGEST_DEMO_DEEP_START_BLOCK
            logger.info(
                "Demo ingest: deep backfill starts at offset block %s (INGEST_DEMO_DEEP_START_BLOCK)",
                deep_start,
            )
        else:
            deep_start = get_next_deep_block() if ARXIV_RESUME_DEEP_SCAN else 1
        offset_blocks: list[int] = []
        if run_deep_backfill:
            if ARXIV_USE_WATERMARK_FRESH:
                # When fresh already covered newest pages, only walk deep pages here.
                offset_blocks = list(range(deep_start, deep_start + ARXIV_SYNC_MAX_OFFSET_BLOCKS))
            else:
                offset_blocks = [0]
                if ARXIV_RESUME_DEEP_SCAN:
                    for b in range(deep_start, deep_start + ARXIV_SYNC_MAX_OFFSET_BLOCKS):
                        if b not in offset_blocks:
                            offset_blocks.append(b)
                else:
                    offset_blocks.extend(range(1, ARXIV_SYNC_MAX_OFFSET_BLOCKS))
            logger.info(
                "Deep backfill plan: blocks=%s (checkpoint deep_start=%s)",
                offset_blocks,
                deep_start,
            )
        else:
            logger.info(
                "Deep backfill skipped (USE_WATERMARK_FRESH=%s RUN_DEEP_BACKFILL=%s cancelled=%s save_cap=%s budget=%s)",
                ARXIV_USE_WATERMARK_FRESH,
                ARXIV_RUN_DEEP_BACKFILL,
                cancelled_early,
                save_cap_reached,
                time_budget_exhausted,
            )

        last_deep_block_seen: int | None = None
        stopped_on_dup_streak = False

        for bi, start_block in enumerate(offset_blocks):
            if pipeline_cancel_requested():
                cancelled_early = True
                logger.info("Pipeline: cancel requested before offset block %s", start_block)
                break
            if (INGEST_TIME_BUDGET_SEC - (time.monotonic() - t0)) <= 0:
                time_budget_exhausted = True
                logger.info(
                    "Pipeline: time budget exhausted before deep block %s — stopping cleanly",
                    start_block,
                )
                break
            if bi > 0:
                _interruptible_sleep(ARXIV_REQUEST_DELAY_SEC)
                if pipeline_cancel_requested():
                    cancelled_early = True
                    logger.info("Pipeline: cancel requested during inter-block sleep")
                    break
            papers, block_meta = fetch_all_bucket_queries(
                max_results_per_query=max_results_per_query,
                start_block=start_block,
                cancel_check=pipeline_cancel_requested,
                interruptible_sleep=_interruptible_sleep,
            )
            # Merge meta: keep cumulative counts across fresh+deep, latest error wins.
            fetch_meta = {
                "requests_ok": int(fetch_meta.get("requests_ok") or 0)
                + int(block_meta.get("requests_ok") or 0),
                "requests_failed": int(fetch_meta.get("requests_failed") or 0)
                + int(block_meta.get("requests_failed") or 0),
                "last_error": block_meta.get("last_error") or fetch_meta.get("last_error"),
                "categories_breaker_tripped": fetch_meta.get("categories_breaker_tripped") or [],
            }
            if papers:
                saw_any_candidates = True
            if pipeline_cancel_requested():
                cancelled_early = True
                logger.info("Pipeline: cancel requested after arXiv fetch")
                break
            logger.info(
                "Pipeline arXiv offset block %s: %s candidate papers",
                start_block,
                len(papers),
            )
            if not papers:
                logger.info("Pipeline: no arXiv candidates at offset block %s; stopping", start_block)
                if start_block > 0:
                    save_next_deep_block(1, run_id=run_id)
                break
            if start_block > 0:
                last_deep_block_seen = start_block
            block_new = 0
            for p in papers:
                if pipeline_cancel_requested():
                    cancelled_early = True
                    logger.info("Pipeline: cancel requested mid-ingest (after %s saves)", saved)
                    break
                if is_duplicate(p["arxiv_id"], db):
                    skipped += 1
                    bump_progress_checkpoint()
                    continue
                pdf_url = p.get("pdf_url") or ""
                if INGEST_FETCH_PDF and pdf_url:
                    full_text = extract_text_from_pdf(pdf_url)
                else:
                    full_text = None
                if pipeline_cancel_requested():
                    cancelled_early = True
                    logger.info(
                        "Pipeline: cancel requested after PDF fetch for %s — skipping save",
                        p.get("arxiv_id"),
                    )
                    break
                full_text = strip_nul_bytes(full_text)
                text = classification_input_text(full_text, p.get("abstract") or "")
                bucket_str, emb = _classify_and_pack(text)
                if pipeline_cancel_requested():
                    cancelled_early = True
                    logger.info(
                        "Pipeline: cancel requested after classify for %s — skipping save",
                        p.get("arxiv_id"),
                    )
                    break
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
            if cancelled_early:
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
                    stopped_on_dup_streak = True
                    break

        if not cancelled_early and ARXIV_RESUME_DEEP_SCAN and last_deep_block_seen is not None:
            if stopped_on_dup_streak or save_cap_reached:
                save_next_deep_block(last_deep_block_seen + 1, run_id=run_id)
            else:
                save_next_deep_block(
                    deep_start + ARXIV_SYNC_MAX_OFFSET_BLOCKS,
                    run_id=run_id,
                )

        if run_id:
            _update_pipeline_run_progress(run_id, saved, skipped, t0)
        if cancelled_early:
            stats: dict[str, Any] = {
                "saved": saved,
                "skipped_duplicates": skipped,
                "backfilled": 0,
            }
            duration_ms = int((time.monotonic() - t0) * 1000)
            err = "Cancelled by user."
            send_pipeline_webhook("cancelled", stats, err, t0)
            _finalize_pipeline_run(
                run_id,
                status="cancelled",
                duration_ms=duration_ms,
                saved=saved,
                skipped=skipped,
                backfilled=0,
                error=err,
            )
            return stats
        if time_budget_exhausted:
            logger.info("Pipeline: time budget exhausted — skipping backfill_classifications this run")
            backfilled = 0
        else:
            backfilled = backfill_classifications(db)
        # backfill_classifications honours pipeline_cancel_requested() and exits
        # early when set. If the user pressed Stop during backfill, finalize the
        # run as cancelled so the UI reflects the user's intent.
        if pipeline_cancel_requested():
            stats = {
                "saved": saved,
                "skipped_duplicates": skipped,
                "backfilled": backfilled,
            }
            duration_ms = int((time.monotonic() - t0) * 1000)
            err = "Cancelled by user during backfill."
            send_pipeline_webhook("cancelled", stats, err, t0)
            _finalize_pipeline_run(
                run_id,
                status="cancelled",
                duration_ms=duration_ms,
                saved=saved,
                skipped=skipped,
                backfilled=backfilled,
                error=err,
            )
            return stats
        stats = {
            "saved": saved,
            "skipped_duplicates": skipped,
            "backfilled": backfilled,
        }
        duration_ms = int((time.monotonic() - t0) * 1000)
        completion_note = _empty_ingest_note(
            saved=saved,
            skipped=skipped,
            saw_candidates=saw_any_candidates,
            fetch_meta=fetch_meta,
            time_budget_exhausted=time_budget_exhausted,
        )
        send_pipeline_webhook("completed", stats, completion_note, t0)
        _finalize_pipeline_run(
            run_id,
            status="completed",
            duration_ms=duration_ms,
            saved=saved,
            skipped=skipped,
            backfilled=backfilled,
            error=completion_note,
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
