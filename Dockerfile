FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# System deps for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (production only)
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    adduser --disabled-password --gecos "" appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Run as non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:create_app", \
     "--factory", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-"]
