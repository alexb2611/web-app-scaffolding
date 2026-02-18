# Web App Scaffolding

Full-stack web application scaffolding designed for rapid project bootstrapping with [Claude Code](https://claude.ai/claude-code) as a development assistant.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16, Alembic, Pydantic v2 |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript 5.7, Tailwind CSS 4, shadcn/ui |
| **Auth** | JWT access + refresh tokens, bcrypt password hashing, rate-limited endpoints |
| **Infra** | Docker Compose, multi-stage Dockerfiles, GitHub Actions CI |

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

docker-compose.yml          # Local dev: PostgreSQL + backend + frontend
Makefile                    # Common command shortcuts
CLAUDE.md                   # Project guide for Claude Code
```

## API Endpoints

All endpoints are under `/api/v1/`:

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/auth/register` | Create account | No |
| `POST` | `/auth/login` | Get access + refresh tokens | No |
| `POST` | `/auth/refresh` | Refresh token pair | No |
| `GET` | `/auth/me` | Current user profile | Bearer |
| `GET` | `/health` | Health check | No |

## Development

### Make shortcuts

```bash
make dev              # docker compose up --build
make down             # docker compose down
make clean            # docker compose down -v (full reset)
make migrate MSG="description"  # Generate + apply Alembic migration
make test             # Run all tests
make lint             # Lint backend + frontend
make format           # Format backend + frontend
make typecheck        # Type check backend + frontend
```

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
