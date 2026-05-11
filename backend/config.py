import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Default DB lives next to backend code when cwd is backend/
_default_db = _BACKEND_DIR / "research_hub.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db}")

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
