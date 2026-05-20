"""Per-category arXiv date watermarks (backend-only — not exposed via HTTP).

Used by the ingest pipeline to ask arXiv only for papers submitted **after** the
last successful save for a given category (minus a safety overlap). This keeps
runs short, avoids 429 rate-limit storms, and makes scheduled runs the source of
truth for new papers.

Schema lives in ``database.CategoryWatermark``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

from database import CategoryWatermark, SessionLocal

logger = logging.getLogger(__name__)


def load_watermarks(categories: Iterable[str]) -> dict[str, date | None]:
    """Return ``{category: watermark_at}`` for the requested categories.

    Categories without a row return ``None`` (treated as "no history yet" — caller
    falls back to a bootstrap window).
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(CategoryWatermark)
            .filter(CategoryWatermark.category.in_(list(categories)))
            .all()
        )
        existing = {r.category: r.watermark_at for r in rows}
        return {cat: existing.get(cat) for cat in categories}
    finally:
        db.close()


def update_watermark(
    category: str,
    max_seen_date: date | None,
    *,
    run_id: int | None = None,
) -> None:
    """Advance ``watermark_at`` to ``max_seen_date`` (only if newer). No-op on None.

    Never moves watermark backwards. Resets the per-category 429 counter on success.
    """
    if max_seen_date is None:
        return
    db = SessionLocal()
    try:
        row = db.get(CategoryWatermark, category)
        if row is None:
            row = CategoryWatermark(
                category=category,
                watermark_at=max_seen_date,
                last_run_id=run_id,
                updated_at=datetime.utcnow(),
                consecutive_429s=0,
            )
            db.add(row)
        else:
            if row.watermark_at is None or max_seen_date > row.watermark_at:
                row.watermark_at = max_seen_date
            row.last_run_id = run_id
            row.updated_at = datetime.utcnow()
            row.consecutive_429s = 0
        db.commit()
        logger.info(
            "Watermark advanced: %s -> %s (run_id=%s)",
            category,
            max_seen_date.isoformat(),
            run_id,
        )
    except Exception:
        logger.exception("Failed to update watermark for %s", category)
        db.rollback()
    finally:
        db.close()


def bump_consecutive_429s(category: str) -> int:
    """Increment 429 counter, return new value. Used by per-category circuit breaker."""
    db = SessionLocal()
    try:
        row = db.get(CategoryWatermark, category)
        if row is None:
            row = CategoryWatermark(
                category=category,
                watermark_at=None,
                consecutive_429s=1,
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            new_val = 1
        else:
            row.consecutive_429s = (row.consecutive_429s or 0) + 1
            row.updated_at = datetime.utcnow()
            new_val = row.consecutive_429s
        db.commit()
        return new_val
    except Exception:
        logger.exception("Failed to bump 429 counter for %s", category)
        db.rollback()
        return 0
    finally:
        db.close()


def reset_consecutive_429s(category: str) -> None:
    """Called after any successful page fetch for the category."""
    db = SessionLocal()
    try:
        row = db.get(CategoryWatermark, category)
        if row is None or (row.consecutive_429s or 0) == 0:
            return
        row.consecutive_429s = 0
        row.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        logger.exception("Failed to reset 429 counter for %s", category)
        db.rollback()
    finally:
        db.close()


def get_consecutive_429s(category: str) -> int:
    db = SessionLocal()
    try:
        row = db.get(CategoryWatermark, category)
        return int(row.consecutive_429s or 0) if row else 0
    finally:
        db.close()
