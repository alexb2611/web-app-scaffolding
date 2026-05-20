# ---------------------------------------------------------------------------
# Backend Dockerfile — multi-stage build
# ---------------------------------------------------------------------------
# Targets:
#   - dev      Local development. Includes pytest / ruff / black / mypy and
#              runs uvicorn with --reload. Used by docker-compose.
#   - runtime  Production image (default — the last stage). Slim, no dev
#              tools, runs as a non-root user.
#
# Build the dev image explicitly:
#   docker build --target dev -t web-app-backend:dev ./backend
#
# Build the production image (defaults to the last stage):
#   docker build -t web-app-backend:latest ./backend
# ---------------------------------------------------------------------------


# ---- base: shared deps + system build chain ------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

# System build deps for asyncpg / psycopg2 wheels.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Hatchling needs the package directory to exist to resolve metadata. The
# real source is bind-mounted in dev / COPY'd in runtime; this stub keeps
# `pip install` happy without invalidating the layer on every source edit.
RUN mkdir -p app && touch app/__init__.py

RUN pip install --no-cache-dir --upgrade pip


# ---- dev: includes test + lint tooling, --reload on, runs as root --------
FROM base AS dev

RUN pip install --no-cache-dir ".[dev]"

EXPOSE 8000

# docker-compose bind-mounts ./backend over /app, so application source is
# the host source at runtime. Python's CWD-on-path resolves `app.main` to
# the mounted source before site-packages — no editable install required.
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]


# ---- builder: production deps only, feeds the runtime stage --------------
FROM base AS builder

RUN pip install --no-cache-dir .


# ---- runtime: slim production image (default target) --------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime dep for asyncpg/psycopg2 (no gcc / libpq-dev — keeps the image slim).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from the *builder* stage, not dev — keeps pytest,
# ruff, black, mypy out of production.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
