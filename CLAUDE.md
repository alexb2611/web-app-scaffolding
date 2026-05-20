# CLAUDE.md — Project Guide for Claude Code

## Project Overview

Full-stack web application scaffolding with FastAPI (Python) backend and Next.js (TypeScript) frontend, designed for rapid project bootstrapping.

> **Adding a new feature?** Read [`docs/adding-a-feature.md`](docs/adding-a-feature.md) first — it's the canonical recipe for adding a user-owned CRUD resource end-to-end (model → migration → service → route → tests → OpenAPI export → Zod schema → form → E2E). The numbered checklist there is the source of truth for the ordering and the conventions; this file documents the building blocks.

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

Both backend and frontend Dockerfiles are multi-stage with a `dev` target (used by `docker-compose`) and a `runtime` target (the default — what production builds). The backend `dev` target installs `[dev]` extras (pytest, ruff, black, mypy) and runs `uvicorn --reload`; `runtime` is the slim production image with none of those tools. This means `make test` / `make lint` / `make typecheck` work against the live compose stack without any extra setup.

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

- **Tests required:** Write or update tests for every code change. Backend changes need pytest tests; frontend changes need type checking at minimum. Changes that affect the auth flow, routing, or page wiring should add or update a Playwright spec in `frontend/e2e/`.
- **Test before commit:** Always run tests and ensure they pass before committing. For backend: `pytest`; for frontend: `npm run typecheck && npm run lint`. Never commit with failing tests.
- **Lint before commit:** Run linting (`ruff check .` for backend, `npm run lint` for frontend) and fix any issues before committing.

## Pre-commit hooks

`.pre-commit-config.yaml` runs hygiene + ruff + black + prettier + eslint on every `git commit`. Full-tree run is ~4.5s.

- **One-time install:** `make install-hooks` (requires `pre-commit` on PATH — `pip install pre-commit` or `pipx install pre-commit`)
- **Manual run:** `make hooks` (same thing CI's `pre-commit` job does)
- **What runs locally:** hygiene hooks (whitespace, EOL, YAML/TOML, merge markers, large files) + ruff (autofix) + black (autofix) + prettier `format:check` + `npm run lint`
- **What's intentionally *not* in pre-commit:** mypy, pytest, `tsc --noEmit`, Playwright. They're slower and CI catches them. Keeping the hook budget under 10s prevents people reaching for `--no-verify`.
- **If a hook autofixes (ruff/black):** the commit fails with files modified in your working tree. Run `git add -u && git commit` to re-commit with the fixes.
- **If a check-only hook fails (prettier/eslint):** run `make format` (prettier) or fix the eslint complaint, then re-commit. We don't autofix frontend files because the npm scripts target the whole dir, which would touch unstaged files.

## Frontend testing layers

Three non-overlapping layers, each with a clear job:

| Tool | Scope | Where |
| --- | --- | --- |
| **TypeScript** (`tsc --noEmit`) | Type drift between layers (API types ↔ Zod ↔ form ↔ UI) | every save / commit |
| **Vitest** | Pure logic — schema validation edges, single-flight refresh, utility functions. Node env, no DOM. | `frontend/src/**/*.test.ts` |
| **Playwright** | UI behavior end-to-end through real browser + real backend | `frontend/e2e/` |

**Choosing between Vitest and Playwright** — if the test needs a browser, real network, or real cookies, it's a Playwright case. If it's pure logic that you can describe with mocks and assertions, it's a Vitest case. When in doubt, lean Vitest — it's orders of magnitude faster and you can run it on every save.

### Unit tests (Vitest)

- **Run locally:** `make test-unit` (one-shot) or `make test-unit-watch` (re-runs on save). Direct: `cd frontend && npm run test:unit`.
- **Colocated**: `auth-schemas.ts` lives next to `auth-schemas.test.ts`. Vitest's `include` pattern is `src/**/*.test.ts`.
- **Explicit imports**: `import { describe, it, expect, vi } from "vitest"` — no magic globals. Matches the project's TS-strict ethos.
- **Mock the global `fetch`** for any test exercising network logic via `vi.stubGlobal("fetch", fn)` + `vi.unstubAllGlobals()` in `afterEach`. The single-flight refresh test in `api.test.ts` is the canonical pattern.
- **Component testing is intentionally not set up.** If a future contributor needs it, install `@testing-library/react` + `jsdom` and switch a single file's environment via `// @vitest-environment jsdom` directive at the top.

### End-to-end tests (Playwright)

Browser-driven auth flow tests live in `frontend/e2e/`. They run against the live docker-compose stack and cover the path pytest can't reach (Next.js proxy + cookies + middleware redirects).

- **Run locally:** `make test-e2e` (requires `make dev` first, plus `RATE_LIMIT_ENABLED=false` in `.env`). `make test-e2e-ui` opens the Playwright UI runner.
- **Selectors:** prefer `getByLabel`, `getByRole({ name })`, `getByText` — resilient against markup tweaks. Don't add `data-testid` unless an accessible selector is genuinely impossible.
- **Isolation:** each test generates a unique email via the `uniqueEmail(label)` helper so the suite is parallel-safe and re-runnable on a non-clean DB.
- **CI:** the `e2e` job in `.github/workflows/ci.yml` brings the full stack up, runs the suite, and uploads `playwright-report/` as an artifact on failure.

## Forms (react-hook-form + Zod + shadcn Form block)

Form state is managed by **react-hook-form**, validated by **Zod** schemas via `@hookform/resolvers/zod`, and rendered through the **shadcn `Form` block** at `frontend/src/components/ui/form.tsx`. Schemas for the auth forms live in `frontend/src/lib/auth-schemas.ts`. The canonical examples are `frontend/src/app/login/page.tsx` and `frontend/src/app/register/page.tsx`.

- **Type alignment with the API contract:** each form schema has an `_AssertX = z.infer<typeof schema> extends components["schemas"]["..."] ? true : never` line — if the OpenAPI contract drifts, the assertion resolves to `never` and TypeScript fails the build. This is how the typed-end-to-end story stays honest from form input through API response.
- **Use the Form block, not raw `register()`.** `<FormField name="..." render={({ field }) => ...} />` is the single source of truth for a field's identity. `FormItem` generates a unique id (`React.useId`), `FormLabel`/`FormControl`/`FormMessage` all consume it for `htmlFor` / `id` / `aria-describedby` / `aria-invalid` automatically. You never repeat the field name and you never wire a11y by hand.
- **Convention:** `useForm({ resolver: zodResolver(schema), mode: "onTouched", defaultValues: {...} })`. Always pass `defaultValues` — Controller-based fields need them and an undefined value throws "uncontrolled to controlled" warnings.
- **Top-level vs field errors:** keep a single `setApiError` state for API-side failures (bad credentials, server down) rendered inside a `<div role="alert">`. Field-level errors are rendered by `<FormMessage />` from RHF's state — no extra plumbing.
- **Don't transform in the schema:** if the output type differs from the input type (`.transform()`, `.pipe()` to a coerced schema, etc.), RHF's `Resolver<TIn, ?, TOut>` becomes awkward. Do post-parse coercion in the submit handler instead (e.g. empty-string → `undefined`).

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
2. **Bump `backend/pyproject.toml`'s `[project] version`.** The version flows through `importlib.metadata.version("app")` to FastAPI's `version=` kwarg and lands in `openapi.json`'s `info.version`. CI's `api-contract` job fails any PR that changes `frontend/openapi.json` without a matching version bump — bump major for breaking changes, minor for additive, patch for internal-only fixes (semver against the OpenAPI surface).
3. Run `make generate-api` (or `python backend/scripts/export_openapi.py - > frontend/openapi.json && cd frontend && npm run generate:api`).
4. Commit `backend/pyproject.toml` + `frontend/openapi.json` + `frontend/src/lib/api-types.ts` alongside the backend change.

Call sites use `unwrap()` from `@/lib/api` to throw `ApiError` on non-2xx responses. The customFetch passed to `createClient` handles auth (Authorization header from in-memory access token), the `X-Request-ID` header, and 401 → refresh → retry.

## Logging

Structured logging via `structlog` (configured in `app/core/logging.py`):
- Dev: `ConsoleRenderer` (pretty + colored). Prod (`ENVIRONMENT=production`): `JSONRenderer`.
- `RequestContextMiddleware` honors incoming `X-Request-ID` or mints a UUID; binds `request_id`, `method`, `path` to `structlog.contextvars`. The ID is echoed back in the response header (`X-Request-ID`) and the frontend surfaces it on `ApiError.requestId`.
- `get_current_user` binds `user_id` once auth resolves, so all downstream logs in that request carry it.
- One `http.request` access log per request with `status` + `duration_ms`. Auth events: `auth.register.success`, `auth.login.success`/`auth.login.failed`, `auth.refresh.success`/`auth.refresh.invalid`/`auth.refresh.reuse_detected` (WARNING — security signal), `auth.logout.success`.

## Observability

OpenTelemetry + Sentry hook points are wired in `app/core/observability.py` and `frontend/sentry.*.config.ts` / `frontend/instrumentation*.ts`. **All opt-in** — nothing fires without explicit env vars, so a default scaffold has no outbound telemetry.

- **Backend traces:** set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` (or any OTLP/HTTP collector). Auto-instruments FastAPI, SQLAlchemy, asyncpg, httpx. For dev visibility without a collector, `OTEL_CONSOLE_EXPORTER=true` prints spans to stdout.
- **Backend errors:** `SENTRY_DSN=...`. Defaults: `send_default_pii=False`, `traces_sample_rate=0.0` (errors only — bump explicitly to enable performance).
- **Frontend errors:** `NEXT_PUBLIC_SENTRY_DSN=...`. Browser + Node + Edge all covered via Next.js's `instrumentation*.ts` convention.
- **Trace/log correlation:** `inject_trace_context` is a structlog processor that surfaces `trace_id` / `span_id` on every log line whenever an OTel span is active. Combined with the existing `request_id` contextvar, you get full cross-referencing between logs, traces, and Sentry events.
