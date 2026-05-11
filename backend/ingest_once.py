"""
CLI entrypoint for the full ingest pipeline (arXiv → dedupe → PDF → classify → SQLite),
plus classification backfill for older rows missing buckets.

Run from repo root:  python backend/ingest_once.py
Or from backend:     python ingest_once.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Allow `python backend/ingest_once.py` (cwd = repo root)
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.chdir(_BACKEND)

from config import ARXIV_MAX_RESULTS  # noqa: E402
from pipeline import run_full_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_once")


def main() -> None:
    per_q = int(os.environ.get("DAY1_MAX_PER_QUERY", str(ARXIV_MAX_RESULTS)))
    stats = run_full_pipeline(max_results_per_query=per_q)
    logger.info("Done. %s", stats)


if __name__ == "__main__":
    main()
