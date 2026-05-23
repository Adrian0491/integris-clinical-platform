FROM python:3.12-slim

# System deps for psycopg2-binary + cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# ---------- Install Python deps first (layer cache) ----------
WORKDIR /tmp
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Copy the full project ----------
# Build context = CDTool project root (set in docker-compose.yml)
WORKDIR /app
COPY . .

# /app        → project root  (bk/, ingest/, mock_data/, backend/)
# PYTHONPATH  → /app (project root) + /app/backend (so `from app.X` works)
ENV PYTHONPATH=/app:/app/backend

# Default: run the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
