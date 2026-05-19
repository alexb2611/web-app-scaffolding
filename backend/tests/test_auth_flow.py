"""End-to-end auth flow tests covering cookie-based refresh + rotation.

These exercise the public contract:
  - Login returns access token in body, refresh token only via HttpOnly cookie.
  - Refresh reads cookie, rotates token, returns new access in body.
  - Replaying an old refresh token revokes the entire token family.
  - Logout revokes the chain and clears cookies.
"""

from typing import Any

import pytest
from httpx import AsyncClient

EMAIL = "alice@example.com"
PASSWORD = "correct-horse-battery-staple"


async def _register(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "Alice"},
    )
    assert res.status_code == 201, res.text


async def _login(client: AsyncClient) -> dict[str, Any]:
    res = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def _set_cookie_header(response: Any, name: str) -> str:
    """Return the Set-Cookie header that begins with `name=`."""
    cookies: list[str] = response.headers.get_list("set-cookie")
    for header in cookies:
        if header.startswith(f"{name}="):
            return header
    raise AssertionError(f"No Set-Cookie for {name!r}. Got: {cookies}")


@pytest.mark.asyncio
async def test_login_returns_access_token_in_body_only(client: AsyncClient) -> None:
    await _register(client)
    res = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # Refresh token MUST NOT appear in the response body.
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_login_sets_httponly_refresh_cookie(client: AsyncClient) -> None:
    await _register(client)
    res = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    refresh_cookie = _set_cookie_header(res, "refresh_token")
    assert "HttpOnly" in refresh_cookie
    assert "SameSite" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie


@pytest.mark.asyncio
async def test_login_sets_auth_present_flag_cookie(client: AsyncClient) -> None:
    """Non-sensitive flag cookie so middleware can route without a credential."""
    await _register(client)
    res = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    flag_cookie = _set_cookie_header(res, "auth_present")
    assert "HttpOnly" not in flag_cookie  # Frontend middleware must be able to read it


@pytest.mark.asyncio
async def test_me_endpoint_with_access_token(client: AsyncClient) -> None:
    await _register(client)
    tokens = await _login(client)
    res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == EMAIL


@pytest.mark.asyncio
async def test_refresh_uses_cookie_and_rotates_token(client: AsyncClient) -> None:
    await _register(client)
    await _login(client)
    original_refresh = client.cookies.get("refresh_token")
    assert original_refresh is not None

    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 200, res.text
    assert "access_token" in res.json()
    # Cookie should be rotated to a new value.
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh is not None
    assert new_refresh != original_refresh


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    res = await client.post("/api/v1/auth/refresh")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_replaying_old_refresh_revokes_entire_family(client: AsyncClient) -> None:
    """Token reuse must invalidate the whole chain — OAuth 2.0 RFC 6819 §5.2.2.3."""
    await _register(client)
    await _login(client)
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh is not None

    # First rotation succeeds.
    first = await client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh is not None and new_refresh != old_refresh

    # Replay the old token — must be rejected.
    client.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401

    # The previously-valid new token is now also revoked (chain revocation).
    client.cookies.set("refresh_token", new_refresh, path="/api/v1/auth")
    after_replay = await client.post("/api/v1/auth/refresh")
    assert after_replay.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_chain_and_clears_cookies(client: AsyncClient) -> None:
    await _register(client)
    await _login(client)
    refresh_before = client.cookies.get("refresh_token")
    assert refresh_before is not None

    res = await client.post("/api/v1/auth/logout")
    assert res.status_code == 204

    # Both cookies should be cleared.
    refresh_clear = _set_cookie_header(res, "refresh_token")
    assert "Max-Age=0" in refresh_clear or "expires=" in refresh_clear.lower()
    flag_clear = _set_cookie_header(res, "auth_present")
    assert "Max-Age=0" in flag_clear or "expires=" in flag_clear.lower()

    # The previously valid refresh token can no longer be used.
    client.cookies.set("refresh_token", refresh_before, path="/api/v1/auth")
    res2 = await client.post("/api/v1/auth/refresh")
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_cookie_is_idempotent(client: AsyncClient) -> None:
    """Calling logout without a session should succeed (no auth required)."""
    res = await client.post("/api/v1/auth/logout")
    assert res.status_code == 204
