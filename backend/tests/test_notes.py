"""End-to-end tests for the Note CRUD endpoints.

These cover:
  - 401 on every endpoint without auth
  - Owner happy paths: create / list / get / update / delete
  - Cross-user access returns 404 (not 403) — the existence-leak
    invariant from the service layer
  - Schema validation: empty title / body rejected
"""

import pytest
from httpx import AsyncClient

PASSWORD = "correct-horse-battery-staple"


async def _make_user_and_login(
    client: AsyncClient, email: str = "owner@example.com"
) -> str:
    """Register + login a user; return the access token."""
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD}
    )
    res = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    token: str = res.json()["access_token"]
    return token


# ---------------------------------------------------------------------------
# Auth requirement
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_note_requires_auth(client: AsyncClient) -> None:
    res = await client.post("/api/v1/notes", json={"title": "x", "body": "y"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_notes_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/notes")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_delete_note_requires_auth(client: AsyncClient) -> None:
    res = await client.delete("/api/v1/notes/some-id")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_then_list_round_trip(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/notes",
        json={"title": "Hello", "body": "World"},
        headers=auth,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Hello"
    assert body["body"] == "World"
    assert "id" in body
    assert "created_at" in body

    listed = await client.get("/api/v1/notes", headers=auth)
    assert listed.status_code == 200
    notes = listed.json()
    assert len(notes) == 1
    assert notes[0]["id"] == body["id"]


@pytest.mark.asyncio
async def test_list_is_newest_first(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    for i in range(3):
        await client.post(
            "/api/v1/notes",
            json={"title": f"Note {i}", "body": "body"},
            headers=auth,
        )

    listed = await client.get("/api/v1/notes", headers=auth)
    titles = [n["title"] for n in listed.json()]
    assert titles == ["Note 2", "Note 1", "Note 0"]


@pytest.mark.asyncio
async def test_get_single_note(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/notes",
        json={"title": "Solo", "body": "Lonely"},
        headers=auth,
    )
    note_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/notes/{note_id}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Solo"


@pytest.mark.asyncio
async def test_patch_updates_only_provided_fields(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/notes",
        json={"title": "Original", "body": "Original body"},
        headers=auth,
    )
    note_id = created.json()["id"]

    # Update only the title — body must survive untouched.
    res = await client.patch(
        f"/api/v1/notes/{note_id}",
        json={"title": "Updated"},
        headers=auth,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Updated"
    assert body["body"] == "Original body"


@pytest.mark.asyncio
async def test_delete_then_get_returns_404(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/notes",
        json={"title": "Doomed", "body": "."},
        headers=auth,
    )
    note_id = created.json()["id"]

    res = await client.delete(f"/api/v1/notes/{note_id}", headers=auth)
    assert res.status_code == 204

    after = await client.get(f"/api/v1/notes/{note_id}", headers=auth)
    assert after.status_code == 404


# ---------------------------------------------------------------------------
# Authorization: cross-user access leaks NO information beyond "not found"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cannot_read_another_users_note(client: AsyncClient) -> None:
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
    # MUST be 404 — never 403, even though the note exists. The 403 would
    # leak that the resource exists; 404 keeps that information opaque.
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_another_users_note(client: AsyncClient) -> None:
    token_a = await _make_user_and_login(client, email="a@example.com")
    created = await client.post(
        "/api/v1/notes",
        json={"title": "secret", "body": "stuff"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    note_id = created.json()["id"]

    token_b = await _make_user_and_login(client, email="b@example.com")
    res = await client.delete(
        f"/api/v1/notes/{note_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 404

    # And the note still exists — user B's attempt didn't accidentally
    # delete it. This guards against query-bug regressions where the
    # `user_id` filter gets dropped.
    still_there = await client.get(
        f"/api/v1/notes/{note_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert still_there.status_code == 200


@pytest.mark.asyncio
async def test_list_only_returns_own_notes(client: AsyncClient) -> None:
    token_a = await _make_user_and_login(client, email="a@example.com")
    await client.post(
        "/api/v1/notes",
        json={"title": "A's note", "body": "."},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    token_b = await _make_user_and_login(client, email="b@example.com")
    res = await client.get(
        "/api/v1/notes", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code == 200
    assert res.json() == []  # B has no notes; A's are filtered out


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_title_rejected(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    res = await client.post(
        "/api/v1/notes",
        json={"title": "", "body": "ok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_empty_body_rejected(client: AsyncClient) -> None:
    token = await _make_user_and_login(client)
    res = await client.post(
        "/api/v1/notes",
        json={"title": "ok", "body": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
