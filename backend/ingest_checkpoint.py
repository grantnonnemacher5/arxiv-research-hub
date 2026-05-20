"""Persist arXiv pagination cursor so deep ingest resumes instead of re-scanning duplicates."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from database import IngestCheckpoint, SessionLocal

logger = logging.getLogger(__name__)

_CHECKPOINT_ID = 1


def get_next_deep_block() -> int:
    """Offset block for older papers (block 0 is always scanned separately for new submissions)."""
    db = SessionLocal()
    try:
        row = db.get(IngestCheckpoint, _CHECKPOINT_ID)
        if row is None:
            return 1
        return max(1, int(row.next_deep_block or 1))
    finally:
        db.close()


def save_next_deep_block(block: int, *, run_id: int | None = None) -> None:
    """Store where the next run should continue deep pagination."""
    block = max(1, int(block))
    db = SessionLocal()
    try:
        row = db.get(IngestCheckpoint, _CHECKPOINT_ID)
        if row is None:
            row = IngestCheckpoint(id=_CHECKPOINT_ID, next_deep_block=block)
            db.add(row)
        else:
            row.next_deep_block = block
        row.updated_at = datetime.utcnow()
        if run_id is not None:
            row.last_run_id = run_id
        db.commit()
        logger.info("Ingest checkpoint: next deep block = %s (run_id=%s)", block, run_id)
    except Exception:
        logger.exception("Failed to save ingest checkpoint")
        db.rollback()
    finally:
        db.close()


def checkpoint_status() -> dict:
    db = SessionLocal()
    try:
        row = db.get(IngestCheckpoint, _CHECKPOINT_ID)
        if row is None:
            return {"next_deep_block": 1, "updated_at": None, "last_run_id": None}
        return {
            "next_deep_block": int(row.next_deep_block or 1),
            "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
            "last_run_id": row.last_run_id,
        }
    finally:
        db.close()
