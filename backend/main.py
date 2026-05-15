"""FastAPI app (plan Day 2)."""

from __future__ import annotations

import logging
import re
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from classifier import BUCKET_DESCRIPTIONS
from config import ARXIV_MAX_RESULTS, CORS_ORIGINS, INGEST_FETCH_PDF, REPORTS_DIR
from database import Paper, PipelineRun, Report, SessionLocal, get_db, init_db
from pipeline import (
    close_stale_running_pipeline_runs,
    pipeline_is_busy,
    request_pipeline_cancel,
    run_full_pipeline,
)
from report_generator import ALLOWED_PERIODS, generate_report
from scheduler import shutdown_scheduler, start_scheduler
from search_hybrid import run_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    stale = close_stale_running_pipeline_runs()
    if stale:
        logger.info(
            "Marked %s pipeline run(s) failed (were still 'running' after last crash/deploy)",
            stale,
        )
    logger.info("INGEST_FETCH_PDF=%s", INGEST_FETCH_PDF)
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="AI Research Knowledge Hub", lifespan=lifespan)


@app.get("/health")
def health():
    """Liveness check for load balancers (Render, etc.). No DB or OpenAI required."""
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Production + preview/branch deploys use different *.vercel.app hosts; list alone misses them.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bucket_counts(db: Session) -> dict[str, int]:
    counts = {name: 0 for name in BUCKET_DESCRIPTIONS}
    for row in db.scalars(select(Paper)).all():
        for part in (x.strip() for x in (row.buckets or "").split(",") if x.strip()):
            if part in counts:
                counts[part] += 1
    return counts


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Paper)) or 0
    today = date.today()
    today_count = (
        db.scalar(
            select(func.count())
            .select_from(Paper)
            .where(cast(Paper.created_at, Date) == today)
        )
        or 0
    )
    return {
        "total_papers": int(total),
        "papers_today": int(today_count),
        "buckets": _bucket_counts(db),
    }


def _utc_iso(dt: datetime | None) -> str | None:
    """Serialize DB datetimes as UTC ISO with Z so browsers parse them correctly."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


@app.get("/pipeline-runs")
def list_pipeline_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recent ingest pipeline executions for ops / failure visibility (paginated, newest first)."""
    total = db.scalar(select(func.count()).select_from(PipelineRun)) or 0
    offset = (page - 1) * page_size
    rows = list(
        db.scalars(
            select(PipelineRun)
            .order_by(PipelineRun.finished_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "items": [
            {
                "id": r.id,
                "started_at": _utc_iso(r.started_at),
                "finished_at": _utc_iso(r.finished_at),
                "trigger": r.trigger,
                "status": r.status,
                "saved": r.saved,
                "skipped_duplicates": r.skipped_duplicates,
                "backfilled": r.backfilled,
                "duration_ms": r.duration_ms,
                "error": r.error,
            }
            for r in rows
        ],
    }


@app.get("/search")
def search_corpus(
    q: str = Query(..., min_length=1, max_length=500),
    mode: str = Query("hybrid", description="keyword | semantic | hybrid"),
    bucket: str | None = Query(None, description="Filter: bucket label substring"),
    limit: int = Query(15, ge=1, le=50),
    rerank: bool = Query(False, description="Hybrid only: blend dense + token overlap on top pool"),
    db: Session = Depends(get_db),
):
    """Hybrid search: SQL keyword match + dense retrieval (pgvector HNSW on Postgres when populated, else capped in-memory cosine), fused with RRF; optional rerank."""
    if mode not in ("keyword", "semantic", "hybrid"):
        raise HTTPException(400, detail="mode must be keyword, semantic, or hybrid")
    try:
        return run_search(db, q, mode, bucket, limit, rerank)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e)) from e


@app.get("/papers")
def list_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    bucket: str | None = None,
    q: str | None = Query(None, description="Keyword search in title, authors, abstract, arXiv id"),
    db: Session = Depends(get_db),
):
    count_stmt = select(func.count()).select_from(Paper)
    stmt = select(Paper).order_by(Paper.created_at.desc())
    if bucket:
        bf = Paper.buckets.contains(bucket)
        count_stmt = count_stmt.where(bf)
        stmt = stmt.where(bf)
    if q and (needle := q.strip()[:500]):
        search = or_(
            Paper.title.contains(needle),
            Paper.authors.contains(needle),
            Paper.abstract.contains(needle),
            Paper.arxiv_id.contains(needle),
        )
        count_stmt = count_stmt.where(search)
        stmt = stmt.where(search)
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    rows = list(db.scalars(stmt.offset(offset).limit(page_size)).all())
    return {
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "items": [
            {
                "id": p.id,
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "published_date": p.published_date.isoformat() if p.published_date else None,
                "buckets": p.buckets,
                "pdf_url": p.pdf_url,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ],
    }


@app.post("/generate-report/{period}")
def generate_report_route(period: str, db: Session = Depends(get_db)):
    if period not in ALLOWED_PERIODS:
        raise HTTPException(400, detail=f"period must be one of {sorted(ALLOWED_PERIODS)}")
    try:
        filename = generate_report(period, db)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e)) from e
    return {"filename": filename, "url": f"/reports/{filename}"}


@app.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).order_by(Report.generated_at.desc()).limit(200)).all()
    return [
        {
            "id": r.id,
            "period": r.period,
            "filename": r.file_path,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in rows
    ]


def _safe_report_path(filename: str) -> Path | None:
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not re.match(r"^[a-zA-Z0-9_.-]+\.html$", filename):
        return None
    base = REPORTS_DIR.resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


@app.get("/reports/{filename}")
def serve_report(filename: str, db: Session = Depends(get_db)):
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(404, detail="Report not found")
    if not re.match(r"^[a-zA-Z0-9_.-]+\.html$", filename):
        raise HTTPException(404, detail="Report not found")
    row = db.scalar(select(Report).where(Report.file_path == filename))
    if row and (html := (row.html_content or "").strip()):
        return Response(content=html, media_type="text/html; charset=utf-8")
    path = _safe_report_path(filename)
    if path is None:
        raise HTTPException(404, detail="Report not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


def _manual_pipeline_thread_target() -> None:
    try:
        run_full_pipeline(max_results_per_query=ARXIV_MAX_RESULTS, trigger="manual")
    except Exception:
        logger.exception("Manual pipeline background thread failed")


@app.get("/pipeline-status")
def pipeline_status():
    """Whether a sync is currently holding the pipeline lock (ingest or backfill)."""
    return {"busy": pipeline_is_busy()}


@app.post("/cancel-pipeline")
def cancel_pipeline_endpoint():
    """Cooperative cancel: pipeline stops between papers / offset blocks."""
    if not pipeline_is_busy():
        raise HTTPException(
            status_code=409,
            detail="No sync is running — nothing to cancel.",
        )
    request_pipeline_cancel()
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": "Stop requested. Ingest will finish the current paper (if any), then exit.",
        },
    )


@app.post("/run-pipeline")
def run_pipeline_endpoint():
    if pipeline_is_busy():
        raise HTTPException(
            status_code=409,
            detail=(
                "A sync is already running. Wait for it to finish, then refresh Pipeline runs "
                "or dashboard stats."
            ),
        )
    threading.Thread(
        target=_manual_pipeline_thread_target,
        name="manual-arxiv-pipeline",
        daemon=False,
    ).start()
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "message": (
                "Sync started on the server. It can take several minutes (arXiv rate limits). "
                "Refresh Pipeline runs or stats for progress; you can leave this page."
            ),
        },
    )
