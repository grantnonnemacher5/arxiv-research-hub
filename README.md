---
title: arXiv Research Hub
emoji: "\U0001F4DA"
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# arxiv-research-hub

Source: [github.com/Yonas1219/arxiv-research-hub](https://github.com/Yonas1219/arxiv-research-hub)

## Setup

```bash
git clone https://github.com/Yonas1219/arxiv-research-hub.git
cd arxiv-research-hub

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

Create a `.env` file at the repo root for secrets—never commit it. Variable names and defaults are in `backend/config.py`.

### Database

- **Local default:** SQLite at `backend/research_hub.db` (no env needed).
- **Production (current):** **Neon Postgres** — set `DATABASE_URL` on the API host (e.g. Render) to the connection string from the Neon dashboard. Prefer URLs that include **`sslmode=require`** when Neon recommends SSL. Driver form: `postgresql+psycopg2://...` (see `backend/config.py`; bare `postgres://` is normalized).

On first startup with a new empty database, `init_db()` runs **`create_all`** so tables (`papers`, `reports`, `pipeline_runs`, `report_llm_cache`, …) appear automatically—no manual SQL migration for the MVP.

**Semantic search at scale (PostgreSQL only):** when `DATABASE_URL` is Postgres (e.g. Neon), the API enables the **`vector`** extension, adds `papers.embedding_vec`, and builds an **HNSW** index. New ingests sync vectors automatically. **Existing** rows that only have blob embeddings need a one-time backfill:

```bash
cd backend && python3 backfill_pgvector.py
```

**Buckets without an OpenAI key:** ingest and `python3 backfill_classifications.py` use **keyword overlap** against the three theme descriptions (no API). Quality is lower than embedding-based tagging. **Embeddings** still require `OPENAI_API_KEY` (then run `backfill_pgvector.py` on Postgres when blobs exist).

Tune with `SEARCH_PGVECTOR_CANDIDATES`, `OPENAI_EMBED_DIMENSION` (must match `OPENAI_EMBED_MODEL`), and `SEARCH_USE_PGVECTOR` — see `backend/config.py`. SQLite stays on in-memory dense scan.

For Postgres **locally** only, you can use Compose and match `docker-compose.yml`:

```bash
docker compose up -d
```

Example line for `.env` when using the bundled Compose Postgres:

```
DATABASE_URL=postgresql+psycopg2://arxiv:arxiv_local_dev@127.0.0.1:5432/research_hub
```

Other hosted providers (Supabase, Railway, …) use the same **`DATABASE_URL`** pattern on the API service.

## Run

Backend (terminal 1):

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm run dev
```

UI: http://localhost:5173. If your API isn’t on port 8000, tell Vite where it is, e.g. `VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev`.

**Vercel (production):** Prefer **`VITE_API_BASE_URL`** in the Vercel project (Settings → Environment Variables) set to your Render URL, then redeploy. If that env never applies to the build, `frontend/src/api.js` falls back to **`PRODUCTION_API_FALLBACK`** in production only—edit that constant if your Render hostname changes.

Optional—one-off ingest from the shell:

```bash
source .venv/bin/activate
cd backend
python ingest_once.py
```

## Layout

```
arxiv-research-hub/
├── backend/           # FastAPI, ingest pipeline, DB models
├── frontend/          # Vite + React
├── reports/           # generated HTML (gitignored)
├── docker-compose.yml # local Postgres if you want it
├── Dockerfile         # API image for Render / Fly / Railway
├── requirements.txt
├── README.md
└── .gitignore
```
