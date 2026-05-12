"""Outbound webhook for pipeline success/failure (PM: integrate first)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from config import WEBHOOK_SECRET, WEBHOOK_URL

logger = logging.getLogger(__name__)


def send_pipeline_webhook(
    status: str,
    stats: dict[str, Any] | None,
    error_message: str | None,
    started_monotonic: float,
) -> None:
    """
    POST JSON to WEBHOOK_URL if set. Never raises — logs delivery failures.

    Payload keys: event, status, timestamp (UTC ISO), source, duration_ms, stats, error.
    Optional header X-Webhook-Secret when WEBHOOK_SECRET is set.
    """
    url = WEBHOOK_URL
    if not url:
        return
    duration_ms = max(0, int((time.monotonic() - started_monotonic) * 1000))
    event = "pipeline.completed" if status == "completed" else "pipeline.failed"
    payload = {
        "event": event,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "arxiv-research-hub",
        "duration_ms": duration_ms,
        "stats": stats,
        "error": error_message,
    }
    headers = {"Content-Type": "application/json"}
    if WEBHOOK_SECRET:
        headers["X-Webhook-Secret"] = WEBHOOK_SECRET
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=15.0)
        r.raise_for_status()
        logger.info("Webhook %s delivered (%s)", event, r.status_code)
    except Exception:
        logger.exception("Webhook delivery failed for %s", event)
