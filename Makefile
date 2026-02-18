# ---------------------------------------------------------------------------
# Makefile — common development shortcuts
# ---------------------------------------------------------------------------

.PHONY: dev down build logs migrate test lint format clean

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
	cd frontend && npm run typecheck

test-backend:
	docker compose exec backend pytest -v

test-cov:
	docker compose exec backend pytest --cov=app --cov-report=term-missing

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
