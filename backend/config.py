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
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(_PROJECT_ROOT / "reports")))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ~8000 tokens heuristic (no tiktoken in Day 1 deps)
FULL_TEXT_MAX_CHARS = int(os.getenv("FULL_TEXT_MAX_CHARS", "32000"))

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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
CLASSIFIER_THRESHOLD = float(os.getenv("CLASSIFIER_THRESHOLD", "0.35"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
