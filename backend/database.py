from datetime import date, datetime
import logging
from typing import Generator

from sqlalchemy import Date, DateTime, Integer, LargeBinary, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import DATABASE_URL

logger = logging.getLogger(__name__)


def strip_nul_bytes(text: str | None) -> str | None:
    """PostgreSQL rejects NUL (0x00) in text; SQLite often accepts it. PDFs/XML can contain NUL."""
    if text is None:
        return None
    return text.replace("\x00", "") if "\x00" in text else text


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    abstract: Mapped[str] = mapped_column(Text, default="")
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str] = mapped_column(Text, default="")
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    buckets: Mapped[str] = mapped_column(Text, default="")  # Day 2 fills; comma-separated
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(8), index=True)
    file_path: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Full HTML persisted for hosts with ephemeral disk (e.g. Render); serve via GET /reports/{filename}
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)


class PipelineRun(Base):
    """One row per ingest pipeline execution (manual or scheduled)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
    trigger: Mapped[str] = mapped_column(String(16))  # manual | scheduled
    status: Mapped[str] = mapped_column(String(16), index=True)  # running | completed | failed
    saved: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    backfilled: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportLlmCache(Base):
    """Cached GPT sections for HTML reports (same window + papers + model → skip LLM)."""

    __tablename__ = "report_llm_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    signature: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    period: Mapped[str] = mapped_column(String(8), index=True)
    content_json: Mapped[str] = mapped_column(Text)
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_reports_html_column() -> None:
    """Add reports.html_content on existing DBs (create_all does not alter tables)."""
    try:
        insp = inspect(engine)
        if not insp.has_table("reports"):
            return
        if any(c["name"] == "html_content" for c in insp.get_columns("reports")):
            return
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE reports ADD COLUMN html_content TEXT"))
        logger.info("Added reports.html_content for persisted HTML exports")
    except Exception:
        logger.exception("Could not add reports.html_content column")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_reports_html_column()
    try:
        from pgvector_support import ensure_pgvector_schema

        ensure_pgvector_schema(engine)
    except Exception:
        logger.exception("Optional pgvector schema step failed (OK on SQLite)")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
