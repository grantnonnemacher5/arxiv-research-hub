# arxive_mvp

Repo: [https://github.com/Yonas1219/arxive_mvp](https://github.com/Yonas1219/arxive_mvp)

## Setup

```bash
git clone https://github.com/Yonas1219/arxive_mvp.git
cd arxive_mvp

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

Add a **`.env`** in the project root for secrets (never commit it). Variable names and defaults are in **`backend/config.py`**.

## Run

**1. API (terminal 1)**

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**2. Dashboard (terminal 2)**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. If the API is not on port 8000, start Vite with e.g. `VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev`.

**3. Optional: ingest from the CLI**

```bash
source .venv/bin/activate
cd backend
python ingest_once.py
```

## Folder structure

```
arxive_mvp/
├── backend/           # FastAPI app, pipeline, SQLite models
├── frontend/          # Vite + React UI
├── reports/           # Generated HTML (created at runtime; gitignored)
├── plan.md
├── requirements.txt
├── README.md
└── .gitignore
```
