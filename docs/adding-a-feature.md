# Adding a feature: an end-to-end recipe

This walks through adding a typical user-owned CRUD resource — call it `Note` — from empty database to passing E2E test. The same shape applies to any auth-protected resource you'd add to this scaffold.

The point isn't to read the file top-to-bottom — it's to use the **checklist** below as a working ticklist while you write the feature, and dip into the relevant section when you need the pattern for that layer.

## Checklist

Copy this into your PR description or branch notes:

```
Backend
  [ ] 1. Model        — backend/app/models/<feature>.py
  [ ] 2. Register     — backend/app/models/__init__.py
  [ ] 3. Migration    — alembic autogenerate + upgrade
  [ ] 4. Schemas      — backend/app/schemas/<feature>.py
  [ ] 5. Service      — backend/app/services/<feature>_service.py
  [ ] 6. Routes       — backend/app/api/v1/<feature>.py + register in v1/__init__.py
  [ ] 7. Tests        — backend/tests/test_<feature>.py

Contract handoff
  [ ] 8. Regenerate   — make generate-api  (commits openapi.json + api-types.ts)

Frontend
  [ ] 9. Zod schema   — frontend/src/lib/<feature>-schemas.ts (with _Assert*)
  [ ] 10. Page/UI     — frontend/src/app/<feature>/page.tsx (or component)
  [ ] 11a. Unit tests — frontend/src/lib/<feature>-schemas.test.ts (Vitest)
  [ ] 11b. E2E spec   — frontend/e2e/<feature>.spec.ts (Playwright)

Gates
  [ ] 12. make hooks && make test && make test-e2e
```

The numbering is the dependency order. Don't skip ahead — step 8 in particular is **load-bearing**: without it the frontend Zod schemas in step 9 won't compile because they reference `components["schemas"]["..."]` from the regenerated `api-types.ts`.

---

## 1. Model

`backend/app/models/note.py` (new file). Pattern: see `backend/app/models/user.py`.

```python
"""SQLAlchemy Note model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

Conventions baked in:

- **UUID-string primary key**, not integer — keeps IDs opaque to clients and avoids enumeration-attack surface.
- **`ondelete="CASCADE"` on the user FK** — when a user is deleted, their notes go with them.
- **`index=True` on the FK** — every `WHERE user_id = ?` query needs it, and the query planner won't add it for you.
- **`created_at` / `updated_at` defaults** — use `lambda: datetime.now(UTC)` (Python-side) not `server_default=func.now()`. Matches the existing `User` model so timezone handling stays consistent.

## 2. Register the model

`backend/app/models/__init__.py`. **Alembic's autogenerate only sees models that are imported here** — forget this and your migration will be empty (a classic 30-minute debug if you don't know to look).

```python
from app.models.note import Note  # add this line
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = ["Note", "RefreshToken", "User"]
```

## 3. Migration

From the host:

```bash
docker compose exec backend alembic revision --autogenerate -m "add notes table"
docker compose exec backend alembic upgrade head
```

Inspect the generated `backend/alembic/versions/<hash>_add_notes_table.py` before applying — autogenerate is usually right but occasionally needs hand-edits (rename detection, complex `op.alter_column`, custom indexes). The diff between the schema and the model is in plain Python.

## 4. Pydantic schemas

`backend/app/schemas/note.py` (new file). Pattern: see `backend/app/schemas/auth.py`.

```python
"""Pydantic schemas for the Note resource."""

from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1)


class NoteResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

Conventions:

- **Three schemas per resource**: `Create` (POST body), `Update` (PATCH body, all fields optional), `Response` (everything the client sees). Even if `Create` and `Response` are identical today, splitting them keeps you from accidentally accepting `id` or `created_at` in a POST body later.
- **`model_config = {"from_attributes": True}`** on response schemas only — this lets FastAPI serialise SQLAlchemy ORM rows directly.
- **`Field(min_length=...)` for validation**, not hand-rolled checks. The constraints flow through to the OpenAPI schema and become available to the frontend Zod definitions in step 9.

## 5. Service layer

`backend/app/services/note_service.py` (new file). All database access lives here, **not in route handlers** — keeps routes thin and lets you test business logic without an HTTP client. Pattern: see `backend/app/services/user_service.py`.

```python
"""Note service — data-access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate


async def create_note(db: AsyncSession, *, user_id: str, data: NoteCreate) -> Note:
    note = Note(user_id=user_id, title=data.title, body=data.body)
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def list_notes_for_user(db: AsyncSession, *, user_id: str) -> list[Note]:
    result = await db.execute(
        select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
    )
    return list(result.scalars().all())


async def get_note_for_user(
    db: AsyncSession, *, note_id: str, user_id: str
) -> Note | None:
    """Authorisation is baked into the query — a note belonging to another
    user returns None, never raises, never leaks existence."""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_note(db: AsyncSession, *, note: Note, data: NoteUpdate) -> Note:
    if data.title is not None:
        note.title = data.title
    if data.body is not None:
        note.body = data.body
    await db.flush()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, *, note: Note) -> None:
    await db.delete(note)
    await db.flush()
```

The load-bearing convention here is **`get_note_for_user(note_id=..., user_id=...)` instead of `get_note(note_id=...)` + a separate auth check.** Bake authorisation into the query so a 404 falls out naturally whether the note doesn't exist or belongs to someone else. The alternative (`get_note` followed by `if note.user_id != current_user.id: raise 403`) leaks existence via the 403-vs-404 distinction.

## 6. Routes

`backend/app/api/v1/notes.py` (new file). Pattern: see `backend/app/api/v1/auth.py`. Then register the router in `backend/app/api/v1/__init__.py`.

```python
"""Note CRUD routes — all auth-protected."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.services import note_service

router = APIRouter(prefix="/notes", tags=["notes"])
_log = structlog.get_logger()


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.create_note(db, user_id=current_user.id, data=payload)
    _log.info("note.created", note_id=note.id)
    return NoteResponse.model_validate(note)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    notes = await note_service.list_notes_for_user(db, user_id=current_user.id)
    return [NoteResponse.model_validate(n) for n in notes]


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return NoteResponse.model_validate(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    payload: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    updated = await note_service.update_note(db, note=note, data=payload)
    return NoteResponse.model_validate(updated)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    note = await note_service.get_note_for_user(
        db, note_id=note_id, user_id=current_user.id
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await note_service.delete_note(db, note=note)
```

Then register:

```python
# backend/app/api/v1/__init__.py
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.notes import router as notes_router  # new

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(notes_router)  # new
```

## 7. Backend tests

`backend/tests/test_notes.py` (new file). Pattern: see `backend/tests/test_auth_flow.py`. **Each request endpoint needs at least: unauthenticated → 401, owner happy path, owner-of-another-user → 404.**

```python
"""End-to-end tests for the Note CRUD endpoints."""

import pytest
from httpx import AsyncClient


async def _make_user_and_login(client: AsyncClient, email: str = "owner@example.com") -> str:
    """Register + login a user; return the access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_create_note_requires_auth(client: AsyncClient) -> None:
    res = await client.post("/api/v1/notes", json={"title": "x", "body": "y"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_then_list_round_trip(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/notes", json={"title": "Hello", "body": "World"}, headers=auth
    )
    assert created.status_code == 201
    assert created.json()["title"] == "Hello"

    listed = await client.get("/api/v1/notes", headers=auth)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_cannot_read_another_users_note(client: AsyncClient) -> None:
    """Cross-user access must return 404, not 403 — see the service layer doc
    for why we don't leak existence."""
    token_a = await _make_user_and_login(client, email="a@example.com")
    created = await client.post(
        "/api/v1/notes",
        json={"title": "secret", "body": "stuff"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    note_id = created.json()["id"]

    token_b = await _make_user_and_login(client, email="b@example.com")
    res = await client.get(
        f"/api/v1/notes/{note_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404  # NOT 403 — we don't want to confirm it exists
```

The `_reset_schema` autouse fixture in `conftest.py` already drops and recreates tables between tests, so each test starts clean without the writer doing anything.

## 8. Regenerate the API contract — DO NOT SKIP

```bash
make generate-api
```

This exports `backend/openapi.json` from the live FastAPI app and regenerates `frontend/src/lib/api-types.ts`. **Both files must be committed alongside your backend changes** — the `api-contract` CI job runs the regeneration and fails on drift.

If you forget this step, the frontend Zod schemas in step 9 won't compile (they reference `components["schemas"]["NoteCreate"]` which won't exist) and you'll be confused for a few minutes wondering why TypeScript thinks NoteCreate isn't a thing.

## 9. Frontend Zod schema

`frontend/src/lib/note-schemas.ts` (new file). Pattern: see `frontend/src/lib/auth-schemas.ts`.

```typescript
import { z } from "zod";

import type { components } from "@/lib/api-types";

export const noteCreateSchema = z.object({
  title: z.string().min(1, "Title is required").max(255, "Title is too long"),
  body: z.string().min(1, "Body is required"),
});

export type NoteCreateInput = z.infer<typeof noteCreateSchema>;

// Compile-time guard. If the OpenAPI contract changes such that
// NoteCreateInput is no longer assignable to NoteCreate, this resolves
// to `never` and the assignment errors at build.
type _AssertCreate =
  NoteCreateInput extends components["schemas"]["NoteCreate"] ? true : never;

const _assertCreate: _AssertCreate = true;
void _assertCreate;
```

This is the load-bearing line in the typed-end-to-end story. If a future contributor renames `body` to `content` on the backend Pydantic schema, regenerates the contract, and forgets to update the Zod schema, the `_AssertCreate` line resolves to `never` and the build fails before a single broken request ships.

## 10. Frontend UI

`frontend/src/app/notes/page.tsx` (new file). Pattern: see `frontend/src/app/dashboard/page.tsx` for auth-gating and `frontend/src/app/login/page.tsx` for the canonical Form + Zod + RHF shape.

Forms use the **shadcn `Form` block** (`src/components/ui/form.tsx`) — `Form` / `FormField` / `FormItem` / `FormLabel` / `FormControl` / `FormMessage`. The block wires up label htmlFor, error-message IDs, `aria-invalid` and `aria-describedby` from a single source: the field's name. You never repeat the field name across `htmlFor`, `id`, `aria-describedby`, and `register("...")` — it lives in one place, on `<FormField name="..." />`.

Skeleton:

```typescript
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { useAuth } from "@/lib/auth";
import { client, unwrap, ApiError } from "@/lib/api";
import { noteCreateSchema, type NoteCreateInput } from "@/lib/note-schemas";
import type { components } from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

type Note = components["schemas"]["NoteResponse"];

export default function NotesPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [apiError, setApiError] = useState("");

  const form = useForm<NoteCreateInput>({
    resolver: zodResolver(noteCreateSchema),
    mode: "onTouched",
    defaultValues: { title: "", body: "" },
  });

  // Auth-gate the page — same pattern as dashboard.
  useEffect(() => {
    if (!isLoading && !user) router.push("/login");
  }, [isLoading, user, router]);

  // Load existing notes once authenticated.
  useEffect(() => {
    if (!user) return;
    void unwrap(client.GET("/api/v1/notes")).then(setNotes).catch(() => {
      /* leave empty on failure */
    });
  }, [user]);

  async function onSubmit(values: NoteCreateInput): Promise<void> {
    setApiError("");
    try {
      const created = await unwrap(
        client.POST("/api/v1/notes", { body: values }),
      );
      setNotes([created, ...notes]);
      form.reset();
    } catch (err) {
      setApiError(err instanceof ApiError ? err.detail : "Something went wrong");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        {apiError && (
          <div role="alert" className="bg-destructive/10 text-destructive ...">
            {apiError}
          </div>
        )}

        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* ...body field, submit button... */}
      </form>
    </Form>
  );
}
```

Two load-bearing things to notice:

- **`client.POST("/api/v1/notes", { body: values })` is fully typed end-to-end.** If the backend renames a field, the `body` argument type changes and TypeScript fails the build at the call site.
- **`<FormField name="title" />` is the single source of truth for the field's identity.** `FormItem` generates a unique id via `React.useId`, `FormLabel` reads it for `htmlFor`, `FormControl` reads it for `id` + `aria-describedby`, `FormMessage` reads it for the error message's id. You never have to type the field name twice, and you never have to think about a11y wiring — it's wired by construction.

## 11. Frontend tests (Vitest + Playwright)

The frontend has two non-overlapping test layers — pick the right one for what you're testing:

| Layer | Use when | Lives in |
| --- | --- | --- |
| **Vitest** (`make test-unit`) | Pure logic — schema validation edges, data transforms, retry/coordination invariants. No DOM, no browser, runs in ~300ms. | `frontend/src/**/*.test.ts` (colocated with the module under test) |
| **Playwright** (`make test-e2e`) | UI behaviour — does the form submit, does the list re-render, does the route protect itself. Browser + real backend. | `frontend/e2e/*.spec.ts` |

**Rule of thumb:** if you can describe the test in terms of inputs and outputs to a pure function or a mockable module, write Vitest. If the assertion needs a real DOM, real network, or real cookies, write Playwright.

### 11a. Vitest — schema validation

`frontend/src/lib/note-schemas.test.ts` (new file). Pattern: see `frontend/src/lib/auth-schemas.test.ts`. Assert on `safeParse` results, including the `error.issues[0].path` so RHF will surface messages on the right field.

```typescript
import { describe, expect, it } from "vitest";
import { noteCreateSchema } from "./note-schemas";

describe("noteCreateSchema", () => {
  it("rejects an empty title with a path-on-title error", () => {
    const result = noteCreateSchema.safeParse({ title: "", body: "x" });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["title"]);
    }
  });
});
```

### 11b. Playwright — UI happy path

`frontend/e2e/notes.spec.ts` (new file). Pattern: see `frontend/e2e/auth.spec.ts`.

Minimal coverage: an authenticated user can create a note and see it in the list. Use the `uniqueEmail` helper to keep tests isolated.

```typescript
import { test, expect } from "@playwright/test";

test("authenticated user creates a note and sees it listed", async ({ page }) => {
  // Register a fresh user — registration auto-logs in.
  const email = `notes-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // Navigate to notes, create one.
  await page.goto("/notes");
  await page.getByLabel("Title").fill("My first note");
  await page.getByLabel("Body").fill("Hello world");
  await page.getByRole("button", { name: /create note/i }).click();

  // It appears in the list.
  await expect(page.getByText("My first note")).toBeVisible();
});
```

## 12. Run the gates

```bash
make hooks                # pre-commit (ruff, black, prettier check, eslint, hygiene)
make test                 # backend pytest + frontend unit tests (Vitest) + typecheck
make test-e2e             # Playwright against the running compose stack
```

All three must pass. Then commit and open the PR. CI will repeat the gates plus add `mypy`, `npm run build`, the api-contract drift check, and the full E2E suite — but if `make hooks && make test && make test-e2e` is green locally, CI is overwhelmingly likely to follow.

---

## Common stumbles

| Symptom | Cause |
| --- | --- |
| `alembic revision --autogenerate` produces an empty migration | Forgot step 2 (`__init__.py` import) — Alembic only sees models that are reachable from the `Base` metadata via import side-effects |
| `npm run typecheck` fails with `Property 'NoteCreate' does not exist on components["schemas"]` | Forgot step 8 (`make generate-api`) — frontend is still working against the old contract |
| Cross-user CRUD test expects 404 but gets 403 | The route is doing `get_note(...)` then a separate authorisation check. Move the user_id filter into the query as in step 5 |
| Playwright test 429s on the auth setup | `RATE_LIMIT_ENABLED=false` not set in `.env` — see `.env.example` |
| `relation "notes" does not exist` at test time | Migration generated but not applied — `docker compose exec backend alembic upgrade head` |

## When to deviate from the recipe

This template is the **paved path**. Deviate when:

- **The resource isn't user-owned** (e.g. a public-read endpoint): drop the `user_id` FK, the `get_current_user` dep on read routes, and the cross-user 404 test. Keep auth on writes.
- **Validation logic is non-trivial**: put it in the service layer behind a function name that describes the business rule (`schedule_meeting`, `transfer_funds`) — Pydantic schemas should stay structural.
- **The frontend needs pagination/filtering**: design that into the route signature (`?cursor=...&limit=...`) before adding it to the UI. The contract is the easiest thing to change before code consumes it.

When in doubt, look at the closest existing pattern in the scaffold and copy it. The codebase is small enough that "find me three places we do X" is a 30-second search, and consistency beats cleverness on a scaffold.
