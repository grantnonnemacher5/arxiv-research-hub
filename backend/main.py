"""FastAPI app (plan Day 2)."""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from classifier import BUCKET_DESCRIPTIONS
from config import ARXIV_MAX_RESULTS, CORS_ORIGINS, REPORTS_DIR
from database import Paper, Report, SessionLocal, get_db, init_db
from pipeline import run_full_pipeline
from report_generator import ALLOWED_PERIODS, generate_report
from scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
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
def serve_report(filename: str):
    path = _safe_report_path(filename)
    if path is None:
        raise HTTPException(404, detail="Report not found")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.post("/run-pipeline")
def run_pipeline_endpoint():
    try:
        stats = run_full_pipeline(max_results_per_query=ARXIV_MAX_RESULTS)
    except Exception as e:
        logger.exception("Manual pipeline failed")
        raise HTTPException(500, detail=str(e)) from e
    return {"status": "ok", "stats": stats}
