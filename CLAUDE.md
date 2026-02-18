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
- `POST /api/v1/auth/login` — Get access + refresh tokens
- `POST /api/v1/auth/refresh` — Refresh token pair
- `GET /api/v1/auth/me` — Current user profile (requires auth)
- `GET /api/v1/health` — Health check
