from datetime import date, datetime
from typing import Generator

from sqlalchemy import Date, DateTime, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import DATABASE_URL


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


_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
