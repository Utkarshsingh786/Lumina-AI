# ─── Backend Dockerfile ───────────────────────────────
# Multi-stage build:
#   development — full dev tools, hot reload, mounted volumes
#   production  — minimal image, no dev tools, pinned deps

FROM python:3.12-slim AS base

# System dependencies for asyncpg, cryptography, python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv==0.5.0

# ── Development ───────────────────────────────────────
FROM base AS development

COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"

# Source is mounted as volume — don't COPY in dev
EXPOSE 8000

# ── Production ────────────────────────────────────────
FROM base AS production

# Copy and install dependencies first (Docker layer caching)
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

# Copy application code
COPY app/ ./app/
COPY alembic.ini .

# Non-root user for security
RUN useradd -m -u 1000 lumina && chown -R lumina:lumina /app
USER lumina

EXPOSE 8000

# Production: multiple uvicorn workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--no-access-log"]
