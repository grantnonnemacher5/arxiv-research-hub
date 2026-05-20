import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any, Callable

import requests

from config import (
    ARXIV_429_BACKOFF_SEC,
    ARXIV_429_MAX_RETRIES,
    ARXIV_MAX_RESULTS,
    ARXIV_PAGE_COUNT,
    ARXIV_QUERIES,
    ARXIV_REQUEST_DELAY_SEC,
    ARXIV_REQUEST_JITTER_SEC,
    ARXIV_SUBMITTED_FROM,
)

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
# arXiv asks clients to identify themselves: https://info.arxiv.org/help/api/user-manual.html
ARXIV_HTTP_HEADERS = {
    "User-Agent": "arxiv-research-hub/1.0 (https://github.com/Yonas1219/arxiv-research-hub; ingest)",
}


def _build_search_query(category_query: str) -> str:
    # From 2020 onward (plan). Spaces around TO work; +TO+ inside brackets triggers arXiv API errors.
    return f"({category_query}) AND submittedDate:[{ARXIV_SUBMITTED_FROM} TO 203012312359]"


def _format_yyyymmddhhmm(d: datetime) -> str:
    """arXiv submittedDate format (UTC). Date-only inputs get 00:00."""
    return d.strftime("%Y%m%d%H%M")


def build_dated_search_query(category_query: str, from_dt: datetime, to_dt: datetime | None = None) -> str:
    """Date-windowed query for the watermark fresh pass.

    ``category_query`` is e.g. ``cat:cs.AI``. ``from_dt`` should already include
    the safety overlap. ``to_dt`` defaults to far-future to capture everything new.
    """
    end = to_dt if to_dt is not None else datetime(2030, 12, 31, 23, 59)
    return (
        f"({category_query}) AND submittedDate:[{_format_yyyymmddhhmm(from_dt)} "
        f"TO {_format_yyyymmddhhmm(end)}]"
    )


def jittered_delay() -> float:
    """Base arXiv delay + small random jitter — desynchronizes co-tenants on shared egress."""
    if ARXIV_REQUEST_JITTER_SEC <= 0:
        return ARXIV_REQUEST_DELAY_SEC
    return ARXIV_REQUEST_DELAY_SEC + random.uniform(0.0, ARXIV_REQUEST_JITTER_SEC)


def _parse_published(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _arxiv_id_from_entry_id(entry_id: str | None) -> str | None:
    if not entry_id:
        return None
    m = re.search(r"arxiv\.org/abs/(.+)$", entry_id.strip())
    if m:
        return m.group(1)
    return None


def _pdf_url_from_entry(entry: ET.Element) -> str | None:
    for link in entry.findall(f"{ATOM}link"):
        if link.get("type") == "application/pdf":
            return link.get("href")
    return None


def _authors(entry: ET.Element) -> str:
    names: list[str] = []
    for author in entry.findall(f"{ATOM}author"):
        name_el = author.find(f"{ATOM}name")
        if name_el is not None and name_el.text:
            names.append(name_el.text.strip())
    return ", ".join(names)


def _entry_to_paper(entry: ET.Element) -> dict[str, Any] | None:
    id_el = entry.find(f"{ATOM}id")
    arxiv_id = _arxiv_id_from_entry_id(id_el.text if id_el is not None else None)
    if not arxiv_id:
        return None

    title_el = entry.find(f"{ATOM}title")
    title = (title_el.text or "").strip().replace("\n", " ")

    summary_el = entry.find(f"{ATOM}summary")
    abstract = (summary_el.text or "").strip() if summary_el is not None else ""

    published_el = entry.find(f"{ATOM}published")
    published = _parse_published(published_el.text if published_el is not None else None)

    pdf_url = _pdf_url_from_entry(entry) or ""

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": _authors(entry),
        "abstract": abstract,
        "published_date": published,
        "pdf_url": pdf_url,
    }


def _retry_after_seconds(response: requests.Response, attempt: int) -> float:
    """Honor Retry-After when present; otherwise exponential backoff."""
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return max(float(raw), ARXIV_REQUEST_DELAY_SEC)
        except ValueError:
            pass
    return max(ARXIV_REQUEST_DELAY_SEC, ARXIV_429_BACKOFF_SEC * (2**attempt))


def fetch_arxiv_papers(
    search_query: str,
    max_results: int | None = None,
    start: int = 0,
    *,
    cancel_check: Callable[[], bool] | None = None,
    interruptible_sleep: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    max_results = max_results if max_results is not None else ARXIV_MAX_RESULTS
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    sleep_fn = interruptible_sleep or time.sleep
    last_response: requests.Response | None = None
    for attempt in range(ARXIV_429_MAX_RETRIES):
        if cancel_check and cancel_check():
            raise RuntimeError("arXiv fetch cancelled")
        if attempt > 0:
            wait = (
                _retry_after_seconds(last_response, attempt - 1)
                if last_response is not None
                else max(ARXIV_REQUEST_DELAY_SEC, ARXIV_429_BACKOFF_SEC * (2 ** (attempt - 1)))
            )
            logger.warning(
                "arXiv rate limited (attempt %s/%s); sleeping %.1fs before retry",
                attempt + 1,
                ARXIV_429_MAX_RETRIES,
                wait,
            )
            sleep_fn(wait)
        response = requests.get(
            ARXIV_API, params=params, headers=ARXIV_HTTP_HEADERS, timeout=60
        )
        last_response = response
        if response.status_code == 429:
            if attempt + 1 >= ARXIV_429_MAX_RETRIES:
                response.raise_for_status()
            continue
        response.raise_for_status()
        root = ET.fromstring(response.content)
        out: list[dict[str, Any]] = []
        for entry in root.findall(f"{ATOM}entry"):
            paper = _entry_to_paper(entry)
            if paper:
                out.append(paper)
        return out
    return []


def fetch_all_bucket_queries(
    max_results_per_query: int | None = None,
    start_block: int = 0,
    cancel_check: Callable[[], bool] | None = None,
    interruptible_sleep: Callable[[float], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch from each configured category; de-dupe by arxiv_id within this run.

    Returns ``(papers, meta)`` where ``meta`` has ``requests_ok``, ``requests_failed``,
    and ``last_error`` (for pipeline diagnostics when saved/skipped stay 0).

    Uses ARXIV_PAGE_COUNT offset pages per category. ``start_block`` shifts the whole window
    deeper (older) by ``start_block * ARXIV_PAGE_COUNT * max_results`` rows per category so sync
    can keep ingesting after the newest pages are already in the database.

    ``cancel_check`` is consulted before each HTTP request so Stop sync exits the
    arXiv loop quickly instead of waiting for every page across every category.
    ``interruptible_sleep`` (defaults to ``time.sleep``) lets the caller break the
    arXiv rate-limit pause early — important because that pause is 3.1 s per
    request and adds up to tens of seconds across categories.
    """
    max_results_per_query = (
        max_results_per_query if max_results_per_query is not None else ARXIV_MAX_RESULTS
    )
    block_stride = ARXIV_PAGE_COUNT * max_results_per_query
    base_start = start_block * block_stride
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"requests_ok": 0, "requests_failed": 0, "last_error": None}
    first_request = True
    sleep_fn = interruptible_sleep or time.sleep
    for q in ARXIV_QUERIES:
        if cancel_check and cancel_check():
            logger.info("arXiv fetch: cancel requested — exiting before next category")
            return merged, meta
        full_q = _build_search_query(q)
        for page in range(ARXIV_PAGE_COUNT):
            if cancel_check and cancel_check():
                logger.info("arXiv fetch: cancel requested — exiting between pages")
                return merged, meta
            if not first_request:
                sleep_fn(ARXIV_REQUEST_DELAY_SEC)
                if cancel_check and cancel_check():
                    logger.info("arXiv fetch: cancel requested after rate-limit sleep")
                    return merged, meta
            first_request = False
            start = base_start + page * max_results_per_query
            try:
                batch = fetch_arxiv_papers(
                    full_q,
                    max_results=max_results_per_query,
                    start=start,
                    cancel_check=cancel_check,
                    interruptible_sleep=sleep_fn,
                )
                meta["requests_ok"] += 1
            except Exception as exc:
                meta["requests_failed"] += 1
                meta["last_error"] = str(exc)[:500]
                logger.error("arXiv fetch failed for %s start=%s: %s", full_q, start, exc)
                break
            if not batch:
                break
            for paper in batch:
                aid = paper["arxiv_id"]
                if aid in seen:
                    continue
                seen.add(aid)
                merged.append(paper)
    return merged, meta
