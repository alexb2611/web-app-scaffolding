# Web App Scaffolding

Full-stack web application scaffolding designed for rapid project bootstrapping with [Claude Code](https://claude.ai/claude-code) as a development assistant.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16, Alembic, Pydantic v2 |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript 5.7, Tailwind CSS 4, shadcn/ui |
| **Auth** | JWT access + refresh tokens, bcrypt password hashing, rate-limited endpoints |
| **Infra** | Docker Compose, multi-stage Dockerfiles (separate dev/runtime targets), GitHub Actions CI |

## Quick Start

```bash
# Clone and enter the project
git clone https://github.com/alexb2611/web-app-scaffolding.git
cd web-app-scaffolding

# Create environment config
cp .env.example .env

# Start all services (PostgreSQL, backend, frontend)
docker compose up --build -d

# Run the initial database migration
docker compose exec backend python -m alembic revision --autogenerate -m "initial"
docker compose exec backend python -m alembic upgrade head
```

The app is now running:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/api/v1
- **API Docs (Swagger):** http://localhost:8000/api/docs

## Project Structure

```
backend/                    # FastAPI application
  app/
    api/v1/                 # Versioned API routes (auth, health)
    core/                   # Config, security (JWT, bcrypt), rate limiting
    db/                     # Async SQLAlchemy engine, session, Base
    models/                 # SQLAlchemy ORM models
    schemas/                # Pydantic request/response schemas
    services/               # Business logic layer
  alembic/                  # Database migrations
  tests/                    # pytest (async)

frontend/                   # Next.js application
  src/
    app/                    # App Router pages and layouts
    components/ui/          # shadcn/ui primitives (source-owned)
    hooks/                  # Custom React hooks
    lib/                    # Utilities, API client, auth context

docs/                       # Contributor docs
  adding-a-feature.md       # End-to-end recipe for adding a user-owned resource
docker-compose.yml          # Local dev: PostgreSQL + backend + frontend
Makefile                    # Common command shortcuts
CLAUDE.md                   # Project guide for Claude Code
```

**New to the scaffold? Start with [docs/adding-a-feature.md](docs/adding-a-feature.md)** — a worked recipe that walks through every layer (model → migration → service → route → tests → OpenAPI export → Zod schema → form → E2E) using a canonical "user-owned CRUD" example. It's the fastest way to learn the conventions without reading every file.

## API Endpoints

All endpoints are under `/api/v1/`:

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/auth/register` | Create account | No |
| `POST` | `/auth/login` | Returns access token; sets HttpOnly refresh cookie | No |
| `POST` | `/auth/refresh` | Rotates refresh cookie; returns new access token | Cookie |
| `POST` | `/auth/logout` | Revokes refresh-token chain, clears cookies | Cookie |
| `GET` | `/auth/me` | Current user profile | Bearer |
| `GET` | `/health` | Health check | No |

The refresh token is delivered via an `HttpOnly; Secure; SameSite` cookie scoped to `/api/v1/auth` — it is never returned in a response body and is invisible to JavaScript. A separate non-sensitive `auth_present=1` cookie lets the Next.js middleware know whether to redirect, without carrying any credential value. Refresh tokens are rotated on every use; presenting a previously-rotated token revokes the entire token family.

## Development

### Pre-commit hooks (recommended one-time setup)

A `pre-commit` config (`.pre-commit-config.yaml`) catches the fastest CI failures locally — hygiene checks (trailing whitespace, EOL, YAML/TOML syntax, large files), `ruff` lint + autofix, `black` format, `prettier` format check, `eslint`. A full run takes ~4.5s, incremental commits faster.

```bash
# One-time install. Requires `pre-commit` on PATH —
# either `pip install pre-commit` / `pipx install pre-commit`,
# or via `pip install -e backend[dev]` if you've set up a host venv.
make install-hooks

# Run all hooks against every tracked file (same thing CI does):
make hooks
```

Slower gates (mypy, pytest, `tsc --noEmit`, Playwright) live in CI only — the pre-commit budget is < 10s so nobody is tempted to `--no-verify`. The `pre-commit` CI job runs the same hooks against `--all-files`, so bypassing locally still fails at PR time.

### Dev vs production images

Both the backend and frontend Dockerfiles are multi-stage with two named targets:

| Target | Used by | Contents |
| --- | --- | --- |
| `dev` | `docker compose up` (local development) | All runtime deps **plus** dev tools (`pytest`, `ruff`, `black`, `mypy` on the backend) and `uvicorn --reload` |
| `runtime` | The default target — what `docker build` produces with no flag, and what you'd push to a registry | Runtime deps only. No dev tools, no build chain, runs as a non-root user |

So `make test`, `make lint`, `make typecheck`, etc. all work against the running compose stack without any extra setup. To explicitly build a slim production image:

```bash
docker build --target runtime -t web-app-backend:prod ./backend
docker build --target runtime -t web-app-frontend:prod ./frontend
```

### Make shortcuts

```bash
make dev              # docker compose up --build
make down             # docker compose down
make clean            # docker compose down -v (full reset)
make migrate MSG="description"  # Generate + apply Alembic migration
make test             # Backend pytest + frontend Vitest + typecheck
make test-unit        # Frontend Vitest only (fast pure-logic tests)
make test-e2e         # Playwright (requires `make dev` + RATE_LIMIT_ENABLED=false)
make lint             # Lint backend + frontend
make format           # Format backend + frontend
make typecheck        # Type check backend + frontend
make generate-api     # Regenerate openapi.json + frontend api-types.ts
```

### Typed API client

The frontend uses [`openapi-fetch`](https://openapi-ts.dev/openapi-fetch/) against types generated from the backend's OpenAPI schema. Every API call has path, body, and response type inference:

```typescript
const tokens = await unwrap(client.POST("/api/v1/auth/login", { body: { email, password } }));
```

After any backend route or schema change, run `make generate-api` and commit the regenerated `frontend/openapi.json` and `frontend/src/lib/api-types.ts`. CI fails on drift.

### Backend (standalone)

Requires a Python 3.12+ virtual environment and a local PostgreSQL instance. Set `DATABASE_URL` in `.env` to point to your local database (replace `db` with `localhost`).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload   # Dev server on :8000
pytest                           # Tests
ruff check .                     # Lint
black .                          # Format
mypy .                           # Type check
```

### Frontend (standalone)

```bash
cd frontend
npm install
npm run dev           # Dev server on :3000
npm run build         # Production build
npm run lint          # ESLint
npm run typecheck     # TypeScript check
npm run format        # Prettier
```

### Frontend unit tests (Vitest)

Fast pure-logic tests live next to the modules they cover (`src/lib/foo.ts` → `src/lib/foo.test.ts`). Scope is **logic Playwright can't easily exercise**: schema validation edges, retry/coordination invariants, utility functions. Node environment, no DOM.

```bash
make test-unit          # one-shot
make test-unit-watch    # re-runs on save
```

The canonical example is `src/lib/api.test.ts` — verifies the single-flight refresh invariant in `tryRefresh` (under parallel pressure, only one `/refresh` call hits the network) by mocking `globalThis.fetch` and stashing the unresolved promise to control timing. That coordination invariant is hard to provoke from a browser test and is the load-bearing case for this layer.

### End-to-end tests (Playwright)

Browser-driven tests covering the full auth flow live in `frontend/e2e/`. They run against the live docker-compose stack and exercise the path that pytest can't reach: Next.js proxy + cookies + token rotation + middleware redirects.

```bash
# 1. Bring up the stack with rate limiting disabled (auth endpoints would
#    otherwise 429 the suite). The .env flag is preserved across runs.
make dev   # docker compose up --build
# (ensure RATE_LIMIT_ENABLED=false is set in .env — see .env.example)

# 2. Run the suite from the host:
make test-e2e            # one-shot run
make test-e2e-ui         # Playwright UI runner — great for debugging
cd frontend && npx playwright show-report   # browse last HTML report
```

Each test generates a unique email so the suite is repeatable on a non-clean database and runs fully in parallel (~8s wall-clock for the auth suite). CI runs the same suite headless against a fresh compose stack and uploads `playwright-report/` as an artifact on failure.

### Observability

Both backend and frontend ship with hook points for OpenTelemetry traces and Sentry error tracking. **Everything is opt-in via env vars** — a default `cp .env.example .env` boot has no outbound telemetry.

| Layer | What | Env to enable |
| --- | --- | --- |
| Backend traces | OTLP/HTTP — works with Tempo, Jaeger, Honeycomb, Datadog, etc. | `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` |
| Backend traces (local dev visibility) | Spans printed to stdout — no collector needed | `OTEL_CONSOLE_EXPORTER=true` |
| Backend errors | Sentry Python SDK | `SENTRY_DSN=https://...` |
| Frontend errors | Sentry Next.js SDK (browser + server + edge) | `NEXT_PUBLIC_SENTRY_DSN=https://...` |

When OpenTelemetry is on, every `structlog` log line gains `trace_id` and `span_id` fields, so logs and traces cross-reference cleanly in any aggregator. FastAPI, SQLAlchemy, asyncpg, and httpx are all auto-instrumented. Browser errors carry the same `X-Request-ID` the backend logs use (via `ApiError.requestId`), so a Sentry breadcrumb in the frontend can be matched to a structured log line on the backend.

### Adding shadcn/ui components

```bash
cd frontend
npx shadcn@latest add button    # Example: add a button component
npx shadcn@latest add dialog    # Components are added to src/components/ui/
```

### Database migrations

```bash
# Inside Docker
docker compose exec backend python -m alembic revision --autogenerate -m "description"
docker compose exec backend python -m alembic upgrade head

# Standalone
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## CI Pipeline

GitHub Actions runs on every push and PR to `main`. All jobs must pass:

| Job | Checks |
|-----|--------|
| **Pre-commit** | Same hooks devs run on `git commit` — hygiene, ruff, black, prettier, eslint |
| **Backend** | `ruff check .` · `black --check .` · `mypy .` · `pytest` (with PostgreSQL service) |
| **Frontend** | `npm run lint` · `npm run typecheck` · `npm run format:check` · `npm run test:unit` (Vitest) · `npm run build` |
| **API contract** | Regenerates OpenAPI schema + TS types from the live backend and fails on drift |
| **E2E** | Boots full docker-compose stack and runs Playwright auth suite against it. Uploads `playwright-report/` on failure |

All backend tools are installed via `pip install -e ".[dev]"`, all frontend tools via `npm ci`. Run `make lint && make format && make typecheck && make test && make test-e2e` locally to catch issues before pushing.

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-...` | JWT signing key (**must change in production**) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Backend URL for frontend API proxy |
| `ENVIRONMENT` | `development` | Set to `production` to hide Swagger docs |

## Using with Claude Code

This project includes a [CLAUDE.md](CLAUDE.md) file that gives Claude Code full context about the project structure, conventions, and commands. Claude works particularly well with this stack because:

- **Python + TypeScript** are Claude's strongest languages
- **FastAPI's type hints** and **Pydantic schemas** give Claude precise type information to reason about
- **shadcn/ui components** live in source (not node_modules), so Claude can read and modify them
- **Tailwind CSS** utility classes are well within Claude's training data

## License

MIT
