# AI Research Knowledge Hub (MVP)

A locally hosted pipeline that pulls academic papers from [arXiv](https://arxiv.org), stores metadata and optional full text in SQLite, and (in later milestones) classifies them into research buckets and generates plain-English reports. See `plan.md` for the full roadmap.

Repository: [https://github.com/Yonas1219/arxive_mvp](https://github.com/Yonas1219/arxive_mvp)

## What this does today

- Queries arXiv (CS + quantitative finance categories, submissions from **2020 onward**).
- **Deduplicates** by arXiv ID before insert.
- **Downloads PDFs** when possible and extracts text with **PyMuPDF** (truncated for downstream limits).
- Persists rows in **SQLite** via SQLAlchemy (`papers` table; `reports` table reserved for generated HTML).

Classification (OpenAI embeddings), GPT report generation, FastAPI, APScheduler, and the React dashboard are **not** wired up yet; they are described in `plan.md` (Days 2–3).

## How to install

Requires **Python 3.11+** (3.12 is fine).

```bash
git clone https://github.com/Yonas1219/arxive_mvp.git
cd arxive_mvp
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a **`.env`** file in the project root (never commit it). Used in later steps for OpenAI; optional for Day‑1 ingest only:

```env
OPENAI_API_KEY=your-key-here
DATABASE_URL=sqlite:///./research_hub.db
ARXIV_MAX_RESULTS=50
SCHEDULE_HOUR=8
REPORTS_DIR=./reports
FULL_TEXT_MAX_CHARS=32000
```

With defaults, the SQLite file is created at `backend/research_hub.db` when you run scripts from `backend/` (see `backend/config.py`).

## How to run (Day 1 ingest test)

```bash
source .venv/bin/activate
cd backend
python ingest_once.py
```

For a smaller first pull, limit results per category:

```bash
DAY1_MAX_PER_QUERY=5 python ingest_once.py
```

arXiv requests are spaced ~3 seconds apart between category queries. PDF downloads can take a while; transient failures leave `full_text` empty while metadata and abstract are still stored.

## How you will use the dashboard (planned)

The React UI will show aggregate stats, bucket breakdown, a searchable paper list, and buttons to generate **7d / 1m / 3m / 6m / 1y** reports. That matches `plan.md` and will connect to FastAPI once Day 2–3 are implemented.

## How reports will work (planned)

Reports will be HTML files under `reports/`, produced from papers in the selected date window and grouped by bucket (General AI, Autonomous Agents, AI x Finance), using GPT‑4o as in the plan.

## Project structure

```
arXiv_MVP/
├── backend/
│   ├── config.py           # env + constants
│   ├── database.py         # SQLAlchemy models + engine
│   ├── arxiv_ingestion.py  # arXiv API client + parsing
│   ├── pdf_extractor.py    # PyMuPDF text extraction
│   ├── deduplicator.py     # arXiv ID duplicate check
│   └── ingest_once.py      # manual end-to-end ingest
├── plan.md
├── requirements.txt
├── README.md
└── .gitignore
```

## Future improvements

- OpenAI embedding classification and bucket labels on each paper.
- GPT‑4o HTML reports and persisted `reports` rows.
- FastAPI service, daily APScheduler job, and React + Tailwind dashboard.
- Retries/backoff for flaky PDF downloads and richer observability.

## License

No license file is included yet; add one in the GitHub UI or as `LICENSE` when you choose terms.
