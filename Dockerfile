# API container — build from repository root: docker build -t arxiv-hub-api .
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1

# Render / Fly / Railway set PORT; local defaults to 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
