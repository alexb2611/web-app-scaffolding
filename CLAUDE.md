# CLAUDE.md — Project Guide for Claude Code

## Project Overview

Full-stack web application scaffolding with FastAPI (Python) backend and Next.js (TypeScript) frontend, designed for rapid project bootstrapping.

## Tech Stack

- **Backend:** FastAPI 0.115+, SQLAlchemy 2.0 (async), PostgreSQL 16, Alembic, Pydantic v2
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript 5.7 (strict), Tailwind CSS 4, shadcn/ui
- **Auth:** JWT access + refresh tokens, bcrypt password hashing
- **Infra:** Docker Compose, multi-stage Dockerfiles

## Project Structure

```
backend/           # FastAPI application
  app/
    api/v1/        # Versioned API routes (auth, health)
    core/          # Config (pydantic-settings), security (JWT, bcrypt)
    db/            # Async SQLAlchemy engine, session, Base
    models/        # SQLAlchemy ORM models
    schemas/       # Pydantic request/response schemas
    services/      # Business logic layer
  alembic/         # Database migrations
  tests/           # pytest (async)

frontend/          # Next.js application
  src/
    app/           # App Router pages and layouts
    components/    # React components
      ui/          # shadcn/ui primitives (source-owned, not node_modules)
    hooks/         # Custom React hooks
    lib/           # Utilities (cn), API client, auth context
```

## Common Commands

### Docker (preferred for full-stack dev)
```bash
cp .env.example .env          # First time setup
docker compose up --build      # Start all services
docker compose down            # Stop all services
```

### Backend (standalone)
Requires a Python 3.12+ venv and a local PostgreSQL. Set `DATABASE_URL` in `.env` to use `localhost` instead of `db`.
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"       # Install with dev dependencies
uvicorn app.main:app --reload # Run dev server on :8000
pytest                         # Run tests
ruff check .                   # Lint
ruff check . --fix             # Lint and auto-fix
black .                        # Format
mypy .                         # Type check
```

### Frontend (standalone)
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Run dev server on :3000
npm run build                  # Production build
npm run lint                   # ESLint
npm run typecheck              # TypeScript check
npm run format                 # Prettier format
```

### Database Migrations
```bash
cd backend
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one step
```

### Make shortcuts
```bash
make dev          # docker compose up --build
make down         # docker compose down
make migrate      # Generate + apply Alembic migration
make test         # Run all tests (backend + frontend)
make lint         # Lint both backend and frontend
make format       # Format both backend and frontend
```

## Coding Conventions

### Backend (Python)
- **Style:** Black formatter (88 char line width), Ruff linter, strict mypy
- **Naming:** snake_case for functions/variables, PascalCase for classes
- **Models:** Use SQLAlchemy `mapped_column()` with explicit types
- **Schemas:** Pydantic v2 with `model_config = {"from_attributes": True}` for ORM models
- **Services:** Business logic lives in `services/`, not in route handlers
- **Dependencies:** Use FastAPI `Depends()` for DB sessions and auth
- **Testing:** pytest with async httpx client, `asyncio_mode = "auto"`

### Frontend (TypeScript)
- **Style:** Prettier (88 char width, trailing commas), ESLint with next/core-web-vitals
- **Naming:** camelCase for functions/variables, PascalCase for components and types
- **Path alias:** Use `@/` imports (maps to `src/`)
- **CSS:** Tailwind CSS utility classes; use `cn()` from `@/lib/utils` for conditional classes
- **Components:** Functional components; use `React.ComponentProps<>` with `&` intersections for prop types (matching shadcn/ui pattern), not separate `interface` declarations
- **shadcn/ui:** new-york style, lucide icons, neutral base color. Components live in `@/components/ui/` as source files — read and modify them freely
- **Adding shadcn/ui components:** Run `npx shadcn@latest add <component>` (e.g., `dialog`, `dropdown-menu`, `toast`)
- **Design tokens:** Use semantic color classes (`text-muted-foreground`, `bg-card`, `border-input`, `bg-destructive/10`, etc.) instead of hardcoded Tailwind colors — this ensures dark mode works via CSS variables in `globals.css`

## Workflow Rules

- **Tests required:** Write or update tests for every code change. Backend changes need pytest tests; frontend changes need type checking at minimum.
- **Test before commit:** Always run tests and ensure they pass before committing. For backend: `pytest`; for frontend: `npm run typecheck && npm run lint`. Never commit with failing tests.
- **Lint before commit:** Run linting (`ruff check .` for backend, `npm run lint` for frontend) and fix any issues before committing.

## Environment Variables

All config is in `.env` (copied from `.env.example`). Key variables:
- `SECRET_KEY` — JWT signing key (MUST change in production)
- `DATABASE_URL` — PostgreSQL connection string (asyncpg driver)
- `CORS_ORIGINS` — Comma-separated allowed origins
- `NEXT_PUBLIC_API_URL` — Backend URL for API proxy rewrites

## API Structure

All endpoints are under `/api/v1/`:
- `POST /api/v1/auth/register` — Create account
- `POST /api/v1/auth/login` — Returns access token in body; sets refresh token as HttpOnly cookie + `auth_present` flag cookie
- `POST /api/v1/auth/refresh` — Rotates the refresh-token cookie; returns new access token in body
- `POST /api/v1/auth/logout` — Revokes the refresh-token chain and clears cookies (204)
- `GET /api/v1/auth/me` — Current user profile (requires auth)
- `GET /api/v1/health` — Health check

**Refresh-token model:** server-side state in `refresh_tokens` table tracks `jti`, family lineage (`replaced_by_id`), and revocation. Presenting a previously-rotated token is treated as compromise and revokes the entire family (per OAuth 2.0 RFC 6819 §5.2.2.3).

## Typed API client

The frontend uses **`openapi-fetch`** with types generated from the backend's OpenAPI schema. Every call site has full path/body/response inference:

```typescript
const tokens = await unwrap(client.POST("/api/v1/auth/login", { body: { email, password } }));
```

**Source of truth:** `frontend/openapi.json` is the committed schema; `frontend/src/lib/api-types.ts` is generated from it. CI fails if either is out of date.

**Workflow when changing the backend contract:**
1. Add/modify routes or Pydantic schemas in `backend/app/`.
2. Run `make generate-api` (or `python backend/scripts/export_openapi.py && cd frontend && npm run generate:api`).
3. Commit `frontend/openapi.json` + `frontend/src/lib/api-types.ts` alongside the backend change.

Call sites use `unwrap()` from `@/lib/api` to throw `ApiError` on non-2xx responses. The customFetch passed to `createClient` handles auth (Authorization header from in-memory access token), the `X-Request-ID` header, and 401 → refresh → retry.

## Logging

Structured logging via `structlog` (configured in `app/core/logging.py`):
- Dev: `ConsoleRenderer` (pretty + colored). Prod (`ENVIRONMENT=production`): `JSONRenderer`.
- `RequestContextMiddleware` honors incoming `X-Request-ID` or mints a UUID; binds `request_id`, `method`, `path` to `structlog.contextvars`. The ID is echoed back in the response header (`X-Request-ID`) and the frontend surfaces it on `ApiError.requestId`.
- `get_current_user` binds `user_id` once auth resolves, so all downstream logs in that request carry it.
- One `http.request` access log per request with `status` + `duration_ms`. Auth events: `auth.register.success`, `auth.login.success`/`auth.login.failed`, `auth.refresh.success`/`auth.refresh.invalid`/`auth.refresh.reuse_detected` (WARNING — security signal), `auth.logout.success`.
