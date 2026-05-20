# ---------------------------------------------------------------------------
# Makefile — common development shortcuts
# ---------------------------------------------------------------------------

.PHONY: dev down build logs migrate test test-unit test-unit-watch test-e2e test-e2e-ui lint format clean generate-api install-hooks hooks

# Start all services
dev:
	docker compose up --build

# Start in background
dev-detached:
	docker compose up --build -d

# Stop all services
down:
	docker compose down

# Stop and remove volumes (full reset)
clean:
	docker compose down -v

# Rebuild containers
build:
	docker compose build

# Follow logs
logs:
	docker compose logs -f

# --- Database ---

# Generate and apply migration (provide MSG="description")
migrate:
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"
	docker compose exec backend alembic upgrade head

# Apply pending migrations
migrate-up:
	docker compose exec backend alembic upgrade head

# Rollback one migration
migrate-down:
	docker compose exec backend alembic downgrade -1

# --- Testing ---

test:
	docker compose exec backend pytest -v
	cd frontend && npm run test:unit
	cd frontend && npm run typecheck

test-backend:
	docker compose exec backend pytest -v

test-cov:
	docker compose exec backend pytest --cov=app --cov-report=term-missing

# Fast pure-logic unit tests via Vitest (no DOM, no browser).
test-unit:
	cd frontend && npm run test:unit

# Vitest in watch mode — re-runs on file change.
test-unit-watch:
	cd frontend && npm run test:unit:watch

# End-to-end browser tests via Playwright. Requires the compose stack to
# already be running (`make dev`) with RATE_LIMIT_ENABLED=false in .env.
test-e2e:
	cd frontend && npx playwright test

# Same suite but with the Playwright UI runner — great for debugging.
test-e2e-ui:
	cd frontend && npx playwright test --ui

# --- Code Quality ---

lint:
	docker compose exec backend ruff check .
	cd frontend && npm run lint

format:
	docker compose exec backend black .
	docker compose exec backend ruff check . --fix
	cd frontend && npm run format

typecheck:
	docker compose exec backend mypy .
	cd frontend && npm run typecheck

# --- Pre-commit hooks ---

# One-time setup. Requires `pre-commit` on PATH (install via `pip install
# pre-commit` or `pipx install pre-commit`, or via `pip install -e
# backend/[.dev]` if you've set up a host venv).
install-hooks:
	pre-commit install

# Run all hooks against every tracked file — same thing CI does.
hooks:
	pre-commit run --all-files

# --- API contract ---

# Regenerate frontend/openapi.json + src/lib/api-types.ts from the backend.
# Run this after any change to the FastAPI routes or Pydantic schemas, then
# commit the regenerated files. CI fails on drift.
generate-api:
	docker compose exec backend python scripts/export_openapi.py
	cd frontend && npm run generate:api
