# ---------------------------------------------------------------------------
# Backend Dockerfile — multi-stage build
# ---------------------------------------------------------------------------
# Stage 1: Install dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies for asyncpg and psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Create minimal package stub so hatchling can resolve dependencies
# (real source is copied in the runtime stage)
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Runtime dependency for asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Run as non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
