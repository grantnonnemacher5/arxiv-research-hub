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

Secrets live in a `.env` file at the repo root. Copy `.env.example` to `.env` and fill it in—don’t commit `.env`. All variable names and defaults are documented in `backend/config.py`.

### Database

Out of the box the API uses SQLite (`backend/research_hub.db`). No extra setup unless you want Postgres.

For Postgres locally, bring up Docker Compose and point `DATABASE_URL` at it (see `.env.example` and `docker-compose.yml`):

```bash
docker compose up -d
cp .env.example .env
# Edit DATABASE_URL if needed so it matches compose.
```

After deploy, hosted providers (Neon, Supabase, Railway, …) give you a URI—use that same `DATABASE_URL` name in Render or wherever the API runs. Tables are created when the app starts (`init_db`).

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
