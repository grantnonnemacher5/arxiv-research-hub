"""Daily APScheduler job for the ingest pipeline (plan Day 2)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE
from pipeline import run_full_pipeline

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _job() -> None:
    try:
        stats = run_full_pipeline()
        logger.info("Scheduled pipeline finished: %s", stats)
    except Exception:
        logger.exception("Scheduled pipeline failed")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _job,
        "cron",
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        id="arxiv_full_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "APScheduler started: daily pipeline at %02d:%02d",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
    )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
