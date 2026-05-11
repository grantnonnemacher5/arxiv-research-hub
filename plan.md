# AI Research Knowledge Hub — Cursor Project Prompt v2
# Based on Final Client Requirements

---

## Project Overview
Build a fully autonomous, locally hosted AI-powered research knowledge hub for a financial services and equity research startup. The system automatically ingests full-text academic papers from arXiv, classifies them into three research buckets, and generates plain-English reports for selected time periods. Everything runs locally — no cloud infrastructure needed for MVP.

---

## Tech Stack
- **Language:** Python 3.11+
- **Backend:** FastAPI
- **Database:** SQLite (via SQLAlchemy)
- **Scheduler:** APScheduler (daily cron job)
- **AI:** OpenAI API (text-embedding-3-small + GPT-4o)
- **PDF Extraction:** PyMuPDF (fitz)
- **HTTP:** requests, httpx
- **Frontend:** React + Tailwind CSS
- **Paper Source:** arXiv API (free, no key needed)
- **Version Control:** GitHub

---

## Research Buckets (Categories)
Every paper must be classified into one or more of these three buckets:

1. **General AI** — Foundation models, LLMs, machine learning, deep learning
2. **Autonomous Agents** — AI agents, multi-agent systems, reinforcement learning, autonomous decision-making
3. **AI x Finance** — AI applied to trading, portfolio management, risk modeling, financial NLP, market prediction

---

## Project Folder Structure

```
research-hub/
├── backend/
│   ├── main.py                  # FastAPI app + API endpoints
│   ├── scheduler.py             # Daily cron job (APScheduler)
│   ├── arxiv_ingestion.py       # Fetch papers from arXiv API
│   ├── pdf_extractor.py         # Download + extract full text from PDFs
│   ├── classifier.py            # OpenAI embeddings + bucket classification
│   ├── report_generator.py      # GPT-4o report generation by time period
│   ├── deduplicator.py          # Basic deduplication logic
│   ├── database.py              # SQLite setup + SQLAlchemy models
│   └── config.py                # API keys, settings, constants
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── Dashboard.jsx        # Main dashboard with stats
│   │       ├── ReportButtons.jsx    # 7d, 1m, 3m, 6m, 1y buttons
│   │       ├── ReportViewer.jsx     # Display generated report
│   │       ├── PaperList.jsx        # List of ingested papers
│   │       └── CategoryBadge.jsx    # Visual bucket label
│   └── package.json
├── reports/                     # Generated reports saved here as HTML
├── requirements.txt
├── .env                         # API keys (never commit this)
├── .gitignore
└── README.md
```

---

## Feature Breakdown

### 1. arXiv Ingestion (`arxiv_ingestion.py`)
- Fetch papers using arXiv API
- Search queries covering all three buckets:
  - `cat:cs.AI` — General AI
  - `cat:cs.LG` — Machine Learning
  - `cat:cs.MA` — Multi-Agent Systems
  - `cat:cs.NE` — Neural/Evolutionary Computing
  - `cat:q-fin.CP` — Computational Finance
  - `cat:q-fin.ST` — Statistical Finance
  - `cat:q-fin.TR` — Trading and Market Microstructure
- Fetch papers from **2020 onward**
- Extract: title, authors, abstract, published date, PDF URL, arXiv ID
- Prefer full-text papers over abstract-only

```python
import requests
import xml.etree.ElementTree as ET

def fetch_arxiv_papers(query, max_results=50):
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    response = requests.get(url, params=params)
    # parse XML response and return list of paper dicts
```

---

### 2. PDF Full-Text Extraction (`pdf_extractor.py`)
- Download PDF from arXiv PDF URL
- Extract full text using PyMuPDF
- Truncate to 8000 tokens for OpenAI processing
- Fall back to abstract if PDF fails

```python
import fitz  # PyMuPDF
import requests

def extract_text_from_pdf(pdf_url: str) -> str:
    try:
        response = requests.get(pdf_url, timeout=15)
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text[:8000]
    except Exception:
        return None  # will fall back to abstract
```

---

### 3. Deduplication (`deduplicator.py`)
- Before saving any paper, check if arXiv ID already exists in database
- If it exists, skip it
- Simple and reliable — no duplicates ever saved

```python
def is_duplicate(arxiv_id: str, db_session) -> bool:
    return db_session.query(Paper).filter_by(arxiv_id=arxiv_id).first() is not None
```

---

### 4. Database (`database.py`)
SQLite database with this schema:

```sql
Table: papers
- id               INTEGER PRIMARY KEY
- arxiv_id         TEXT UNIQUE
- title            TEXT
- authors          TEXT
- abstract         TEXT
- full_text        TEXT
- pdf_url          TEXT
- published_date   DATE
- buckets          TEXT        -- comma separated e.g. "General AI, AI x Finance"
- embedding        BLOB
- created_at       DATETIME

Table: reports
- id               INTEGER PRIMARY KEY
- period           TEXT        -- "7d", "1m", "3m", "6m", "1y"
- file_path        TEXT        -- path to generated HTML report
- generated_at     DATETIME
```

---

### 5. Classification (`classifier.py`)
- Generate embedding for each paper using `text-embedding-3-small`
- Compare against pre-defined bucket description embeddings
- Use cosine similarity to assign one or more buckets
- A paper can belong to multiple buckets

```python
from openai import OpenAI
import numpy as np

BUCKET_DESCRIPTIONS = {
    "General AI": "Large language models, foundation models, deep learning, machine learning, neural networks, computer vision",
    "Autonomous Agents": "AI agents, autonomous systems, multi-agent reinforcement learning, decision making, planning",
    "AI x Finance": "AI in finance, algorithmic trading, portfolio optimization, risk modeling, financial NLP, market prediction"
}

def classify_paper(text: str) -> list[str]:
    # get embedding for paper
    # compare to each bucket embedding
    # return buckets where similarity > threshold (0.35)
```

---

### 6. Report Generator (`report_generator.py`)
- Accept a time period: `7d`, `1m`, `3m`, `6m`, `1y`
- Fetch all papers from that period
- Group papers by bucket
- Use GPT-4o to generate a plain-English research report
- Save report as HTML file in `/reports/` folder
- Report must be ~5 pages max

**Report Structure:**
```
Title: AI Research Report — [Time Period]
Generated: [Date]

Executive Summary (1 paragraph)

---

Section 1: General AI
  - Key Papers (list with title, authors, date)
  - Summary of key themes and findings (GPT-4o generated)

Section 2: Autonomous Agents
  - Key Papers
  - Summary of key themes and findings

Section 3: AI x Finance
  - Key Papers
  - Summary of key themes and findings

---

Total Papers Reviewed: X
Report Generated By: AI Research Hub MVP
```

```python
def generate_report(period: str, db_session) -> str:
    # 1. calculate date range from period
    # 2. fetch papers from that date range
    # 3. group by bucket
    # 4. for each bucket, call GPT-4o to summarize
    # 5. assemble HTML report
    # 6. save to /reports/{period}_{timestamp}.html
    # 7. return file path
```

---

### 7. FastAPI Backend (`main.py`)

```
GET  /stats                      - Total papers, papers today
GET  /papers                     - List all papers (paginated)
GET  /papers?bucket=General+AI   - Filter by bucket
POST /generate-report/{period}   - Generate report (7d/1m/3m/6m/1y)
GET  /reports                    - List all generated reports
GET  /reports/{filename}         - Serve a specific report HTML
POST /run-pipeline               - Manually trigger ingestion
```

---

### 8. Scheduler (`scheduler.py`)
- Run full pipeline every day at 8AM automatically
- Pipeline order:
  1. Fetch new papers from arXiv
  2. Check for duplicates
  3. Extract PDF full text
  4. Generate embeddings + classify into buckets
  5. Save to database

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(run_full_pipeline, 'cron', hour=8, minute=0)
scheduler.start()
```

---

### 9. React Dashboard (`frontend/`)

**Dashboard shows:**
- Total ingested articles (all time)
- Articles ingested today
- Breakdown by bucket (General AI / Autonomous Agents / AI x Finance)

**Report Buttons (5 buttons):**
- Last 7 Days
- Last 1 Month
- Last 3 Months
- Last 6 Months
- Last Year

When clicked:
1. Button calls `POST /generate-report/{period}`
2. Shows loading spinner while generating
3. Opens the generated HTML report in a new tab via local URL

**Paper List:**
- Shows all papers with title, authors, date, bucket badges
- Simple search by keyword

---

## Environment Variables (`.env`)
```
OPENAI_API_KEY=your-openai-api-key-here
DATABASE_URL=sqlite:///./research_hub.db
ARXIV_MAX_RESULTS=50
SCHEDULE_HOUR=8
REPORTS_DIR=./reports
```

---

## Requirements (`requirements.txt`)
```
fastapi
uvicorn
sqlalchemy
apscheduler
openai
pymupdf
requests
httpx
numpy
python-dotenv
```

---

## GitHub Setup
- Create a repo called `research-hub`
- Commit after each major feature
- Suggested commit messages:
  - `feat: arXiv ingestion pipeline`
  - `feat: PDF text extraction`
  - `feat: OpenAI classification into buckets`
  - `feat: report generation with GPT-4o`
  - `feat: FastAPI backend endpoints`
  - `feat: React dashboard with report buttons`
  - `docs: add README and setup instructions`

---

## README Structure
```
# AI Research Knowledge Hub

## What This Does
## How To Install
## How To Run
## How To Use The Dashboard
## How Reports Are Generated
## Project Structure Explained
## Future Improvements
```

---

## Day-by-Day Build Plan

### Day 1 — Backend Foundation
- [ ] Set up project folder and GitHub repo
- [ ] Create virtual environment and install requirements
- [ ] Build `database.py` — SQLite schema and models
- [ ] Build `arxiv_ingestion.py` — fetch and parse papers
- [ ] Build `pdf_extractor.py` — download and extract full text
- [ ] Build `deduplicator.py` — skip existing papers
- [ ] Test: run ingestion manually, verify papers saved in DB

### Day 2 — AI Layer + API
- [ ] Build `classifier.py` — embeddings + bucket classification
- [ ] Build `report_generator.py` — GPT-4o reports for each time period
- [ ] Build `scheduler.py` — daily cron job
- [ ] Build `main.py` — all FastAPI endpoints
- [ ] Test: full pipeline runs, reports generate correctly

### Day 3 — Dashboard + Polish
- [ ] Build React dashboard with stats and report buttons
- [ ] Connect frontend to FastAPI
- [ ] Test all 5 report buttons (7d, 1m, 3m, 6m, 1y)
- [ ] Clean up code, add comments for beginner readability
- [ ] Push final code to GitHub with clean commits
- [ ] Write README with setup instructions

---

## How To Run Locally
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:5173`
API available at: `http://localhost:8000`
Reports available at: `http://localhost:8000/reports/{filename}`

---

## Cursor Instructions
1. Paste this entire prompt into Cursor AI chat
2. Say: "Build this project step by step starting with Day 1"
3. Build and test one file at a time
4. Never hardcode API keys — always use .env
5. After each file is built, ask Cursor to explain what it built in simple terms
6. Commit to GitHub after each completed feature