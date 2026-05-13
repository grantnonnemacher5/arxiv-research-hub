import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
# Repo-root .env (works when cwd is backend/ or project root)
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv()

# Database
# - Local / MVP (default): SQLite file next to this package — no env needed.
# - Production: set DATABASE_URL to PostgreSQL, e.g. from Neon, Supabase, Railway:
#     postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
#   Install deps with `pip install -r requirements.txt` (includes psycopg2-binary).
#   Deploy with a fresh DB: run the API once so tables are created (init_db), or use migrations later.
_default_db = _BACKEND_DIR / "research_hub.db"
_raw_url = os.getenv("DATABASE_URL", f"sqlite:///{_default_db}")
# Some hosts still issue postgres:// URLs; SQLAlchemy expects postgresql://
if _raw_url.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + _raw_url[len("postgres://") :]
else:
    DATABASE_URL = _raw_url

ARXIV_MAX_RESULTS = int(os.getenv("ARXIV_MAX_RESULTS", "50"))
# Per category: pages at max_results each (start=0, then start=max_results, …). >1 reaches older
# submissions when the first page is already fully ingested (common after initial backfill).
ARXIV_PAGE_COUNT = max(1, int(os.getenv("ARXIV_PAGE_COUNT", "2")))
# When an offset block returns only DB duplicates, advance deeper into arXiv (per category) up to this many blocks.
ARXIV_SYNC_MAX_OFFSET_BLOCKS = max(1, int(os.getenv("ARXIV_SYNC_MAX_OFFSET_BLOCKS", "6")))
# Stop after this many consecutive blocks that had candidates but 0 new saves (avoids endless API calls).
ARXIV_SYNC_STOP_ALL_DUP_STREAK = max(1, int(os.getenv("ARXIV_SYNC_STOP_ALL_DUP_STREAK", "3")))
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(_PROJECT_ROOT / "reports")))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ~8000 tokens heuristic (no tiktoken in Day 1 deps)
FULL_TEXT_MAX_CHARS = int(os.getenv("FULL_TEXT_MAX_CHARS", "32000"))
# Backfill loads papers in small chunks to avoid OOM on low-RAM hosts (e.g. Render free ~512MB).
BACKFILL_CLASSIFICATION_BATCH_SIZE = max(1, int(os.getenv("BACKFILL_CLASSIFICATION_BATCH_SIZE", "40")))

ARXIV_QUERIES = [
    "cat:cs.AI",
    "cat:cs.LG",
    "cat:cs.MA",
    "cat:cs.NE",
    "cat:q-fin.CP",
    "cat:q-fin.ST",
    "cat:q-fin.TR",
]

# arXiv submittedDate range: YYYYMMDDHHMM GMT
ARXIV_SUBMITTED_FROM = "202001010000"

# Outbound pipeline notifications (optional). If WEBHOOK_URL is empty, no POST is sent.
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# When true (default), reuse stored GPT sections for a report if inputs unchanged (saves tokens).
REPORT_SUMMARY_CACHE = _env_bool("REPORT_SUMMARY_CACHE", True)

# When true (default), bucket embeddings use abstract only — fewer tokens vs full PDF text.
CLASSIFY_FROM_ABSTRACT = _env_bool("CLASSIFY_FROM_ABSTRACT", True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
CLASSIFIER_THRESHOLD = float(os.getenv("CLASSIFIER_THRESHOLD", "0.35"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

# Hybrid search: keyword pool size and max papers scanned for dense similarity (SQLite / fallback).
SEARCH_KEYWORD_POOL = int(os.getenv("SEARCH_KEYWORD_POOL", "250"))
SEARCH_SEMANTIC_MAX_PAPERS = int(os.getenv("SEARCH_SEMANTIC_MAX_PAPERS", "3000"))
SEARCH_RRF_K = int(os.getenv("SEARCH_RRF_K", "60"))
# PostgreSQL + pgvector: ANN candidate pool for semantic / hybrid dense leg (HNSW index on `embedding_vec`).
SEARCH_USE_PGVECTOR = _env_bool("SEARCH_USE_PGVECTOR", True)
SEARCH_PGVECTOR_CANDIDATES = int(os.getenv("SEARCH_PGVECTOR_CANDIDATES", "400"))
# Must match the embedding model output size (text-embedding-3-small default = 1536).
OPENAI_EMBED_DIMENSION = int(os.getenv("OPENAI_EMBED_DIMENSION", "1536"))

# Default includes the live Vercel origin. If you set CORS_ORIGINS on Render, it replaces this entire list—
# include https://arxiv-research-hub.vercel.app there or leave CORS_ORIGINS unset to use these defaults.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://arxiv-research-hub.vercel.app",
    ).split(",")
    if o.strip()
]
