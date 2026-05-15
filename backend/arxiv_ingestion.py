import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Callable

import requests

from config import ARXIV_MAX_RESULTS, ARXIV_PAGE_COUNT, ARXIV_QUERIES, ARXIV_SUBMITTED_FROM

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def _build_search_query(category_query: str) -> str:
    # From 2020 onward (plan). Spaces around TO work; +TO+ inside brackets triggers arXiv API errors.
    return f"({category_query}) AND submittedDate:[{ARXIV_SUBMITTED_FROM} TO 203012312359]"


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


def fetch_arxiv_papers(
    search_query: str,
    max_results: int | None = None,
    start: int = 0,
) -> list[dict[str, Any]]:
    max_results = max_results if max_results is not None else ARXIV_MAX_RESULTS
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = requests.get(ARXIV_API, params=params, timeout=60)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    out: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        paper = _entry_to_paper(entry)
        if paper:
            out.append(paper)
    return out


def fetch_all_bucket_queries(
    max_results_per_query: int | None = None,
    start_block: int = 0,
    cancel_check: Callable[[], bool] | None = None,
    interruptible_sleep: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch from each configured category; de-dupe by arxiv_id within this run.

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
    first_request = True
    sleep_fn = interruptible_sleep or time.sleep
    for q in ARXIV_QUERIES:
        if cancel_check and cancel_check():
            logger.info("arXiv fetch: cancel requested — exiting before next category")
            return merged
        full_q = _build_search_query(q)
        for page in range(ARXIV_PAGE_COUNT):
            if cancel_check and cancel_check():
                logger.info("arXiv fetch: cancel requested — exiting between pages")
                return merged
            if not first_request:
                sleep_fn(3.1)  # arXiv asks for ~3s between requests
                if cancel_check and cancel_check():
                    logger.info("arXiv fetch: cancel requested after rate-limit sleep")
                    return merged
            first_request = False
            start = base_start + page * max_results_per_query
            try:
                batch = fetch_arxiv_papers(full_q, max_results=max_results_per_query, start=start)
            except Exception as exc:
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
    return merged
