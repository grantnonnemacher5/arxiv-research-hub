# API container — build from repository root: docker build -t arxiv-hub-api .
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Hugging Face Spaces runs the container as a non-root user (UID 1000). Make /app writable
# so PyMuPDF temp files, the SQLite fallback DB, and `reports/` can be created at runtime.
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1

# Render / Fly / Railway inject PORT. Hugging Face Spaces (Docker SDK) expects 7860 by default.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
