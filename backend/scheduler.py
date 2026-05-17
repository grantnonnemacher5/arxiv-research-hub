"""Daily APScheduler job for the ingest pipeline (plan Day 2)."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_TIMEZONE
from pipeline import run_full_pipeline

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _schedule_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(SCHEDULE_TIMEZONE)
    except Exception:
        logger.warning(
            "Invalid SCHEDULE_TIMEZONE=%r — falling back to America/Chicago",
            SCHEDULE_TIMEZONE,
        )
        return ZoneInfo("America/Chicago")


def _job() -> None:
    try:
        stats = run_full_pipeline(trigger="scheduled")
        logger.info("Scheduled pipeline finished: %s", stats)
    except Exception:
        logger.exception("Scheduled pipeline failed")


def start_scheduler() -> None:
    if scheduler.running:
        return
    tz = _schedule_timezone()
    scheduler.add_job(
        _job,
        "cron",
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        timezone=tz,
        id="arxiv_full_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "APScheduler started: daily pipeline at %02d:%02d %s",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
        tz,
    )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
