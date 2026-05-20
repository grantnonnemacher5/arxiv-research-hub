---
title: arXiv Research Hub
emoji: "\U0001F4DA"
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AI Research Knowledge Hub

This project ingests papers from arXiv, stores them in a database, assigns each paper to one or more research themes, and exposes everything through a web app with search and AI written reports. It is built for teams that want a curated library in General AI, Autonomous Agents, and AI x Finance without browsing arXiv manually every day.

Repository: https://github.com/grantnonnemacher5/arxiv-research-hub

What it does

The app syncs on a daily schedule (default 8:00 AM US Central). You can also start a sync from the Pipeline screen. Both use the same backend logic and the same pipeline_runs history table.

Each run fetches only papers we have not stored yet, using a per category date watermark plus a 48 hour safety window for late listings. Runs stop after a time budget (about 10 to 15 minutes by default) or after a maximum number of new saves.

Classification uses OpenAI embeddings when OPENAI_API_KEY is set. Otherwise the app uses simple keyword overlap against three theme descriptions.

Search can be keyword based, semantic, or hybrid. PostgreSQL deployments use pgvector for fast similarity search. SQLite uses a smaller in memory scan, which is fine for local development.

Reports are HTML summaries for the last 7 days, 1 month, 3 months, 6 months, or 1 year. The generator can reuse cached text when the underlying papers and settings have not changed.

The Pipeline screen lists every run: papers saved, duplicates skipped, and duration. You may cancel a running sync. Papers already saved remain in the database.

How it fits together

arXiv provides paper metadata (and optional PDFs). A scheduled job and the manual sync button both call pipeline.py, which classifies and writes to the database. FastAPI in main.py serves JSON to the React app on Vercel. The browser never calls arXiv or OpenAI directly; it only calls our API using VITE_API_BASE_URL at build time.

Stack: Python and FastAPI on the server, React and Vite in the browser, SQLAlchemy for storage, OpenAI for embeddings and report text, PyMuPDF for PDF text, APScheduler for the daily job. Production commonly uses Hugging Face Spaces or Render for the API, Vercel for the frontend, and managed PostgreSQL for data.

Run locally

Install Python 3.11+ and Node 18+. Clone the repo, create a virtualenv, and install dependencies:

```bash
git clone https://github.com/grantnonnemacher5/arxiv-research-hub
cd arxiv-research-hub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Add a .env file at the repo root (never commit it). At minimum you may set OPENAI_API_KEY. For PostgreSQL instead of the default SQLite file, set DATABASE_URL to your connection string.

Start the API:

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Start the UI in another terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. If the API uses another port: `VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev`

One off ingest:

```bash
source .venv/bin/activate
cd backend
python ingest_once.py
```

Configuration

All defaults are in backend/config.py. The most important variables:

DATABASE_URL points at SQLite locally or PostgreSQL in production. OPENAI_API_KEY enables embedding classification, semantic search, and reports. OPENAI_EMBED_MODEL and OPENAI_CHAT_MODEL select which OpenAI models to call. SCHEDULE_HOUR, SCHEDULE_MINUTE, and SCHEDULE_TIMEZONE control the daily job (default 8:00 America/Chicago).

ARXIV_MAX_RESULTS sets page size when calling arXiv. ARXIV_REQUEST_DELAY_SEC and ARXIV_REQUEST_JITTER_SEC pace requests. ARXIV_SYNC_MAX_SAVES_PER_RUN and INGEST_TIME_BUDGET_SEC cap cost and runtime. ARXIV_SAFETY_OVERLAP_HOURS widens the watermark window. ARXIV_USE_WATERMARK_FRESH toggles the newer ingest path. INGEST_FETCH_PDF turns PDF download on or off (off saves RAM on small hosts). SEARCH_USE_PGVECTOR turns on vector search in Postgres. CORS_ORIGINS lists allowed web origins. WEBHOOK_URL and WEBHOOK_SECRET optionally notify an external URL when a run finishes.

The file contains the full list, including retry behavior when arXiv returns rate limits.

Database

Locally the SQLite file appears under backend/research_hub.db. In production use PostgreSQL (Neon, Aiven, Supabase, etc.). On first start the app creates tables for papers, pipeline runs, reports, caches, watermarks, and checkpoints. No separate migration tool is required for this MVP.

On PostgreSQL, run once if older papers need vector columns:

```bash
cd backend && python3 backfill_pgvector.py
```

For Docker based local Postgres:

```bash
docker compose up -d
```

API

With the server running, visit /docs for interactive OpenAPI documentation.

GET /health checks that the process is up.
GET /stats returns counts for the dashboard.
GET /analytics/papers-over-time feeds the chart.
GET /papers lists the library with paging and optional filters.
GET /search queries the corpus (keyword, semantic, or hybrid).
GET /pipeline-runs returns sync history.
GET /pipeline-status reports whether a sync is active.
POST /run-pipeline starts a manual sync.
POST /cancel-pipeline asks the worker to stop after the current paper.
POST /generate-report/{period} builds a report for 7d, 1m, 3m, 6m, or 1y.
GET /reports and GET /reports/{filename} list and open saved reports.

Code layout

backend/ holds the API and ingest pipeline (main.py, pipeline.py, arxiv_ingestion.py, classifier.py, search_hybrid.py, report_generator.py, database.py, scheduler.py, ingest_watermark.py, and helpers).

frontend/ holds the React UI (src/api.js talks to the API; src/pages/ has Dashboard, Papers, Pipeline, and Reports).

docs/ and plan.md explain the product and build process. reports/ stores generated HTML locally and is not committed.

Background jobs

The scheduler calls the same function as the Run Pipeline button. If you scale to multiple API processes, run the scheduler on only one instance.

Ingest walks each arXiv category, advances watermarks after successful pages, and records progress in pipeline_runs. A row is created as soon as a sync starts so the UI can show status. Stale running rows are marked failed after a crash or redeploy.

Deployment

API: build the Dockerfile and deploy to Hugging Face Spaces, Render, or similar. Set OPENAI_API_KEY and DATABASE_URL in the host environment. Health check: GET /health.

Frontend: build with npm run build on Vercel. Set `VITE_API_BASE_URL` in Vercel environment variables to your public API URL (same value as in `.env` for local builds).

Database: create PostgreSQL, set DATABASE_URL on the API service, deploy once so tables and extensions are created.

Maintenance scripts (run from backend/ with venv active)

python ingest_once.py for a single manual sync.
python backfill_classifications.py to fill missing bucket tags.
python backfill_pgvector.py to refresh vector columns.
python backfill_report_html_from_disk.py to attach HTML files to report rows.
python prune_papers.py and python prune_pipeline_runs.py for cleanup (dry run by default on papers).

Roadmap

MVP scope is complete. Future work may include Alembic migrations, a lock so only one replica runs the scheduler, auth on pipeline routes, and more research themes.
