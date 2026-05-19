"""Structured logging + request-ID tests.

Confirms that:
  - Every response carries an X-Request-ID header (generated if absent,
    honored if supplied by the client).
  - An access-log event is emitted with method, path, status, duration.
  - Auth events (success, failure, refresh-reuse) are emitted with the
    request_id (and user_id where applicable) bound in context.
"""

from collections.abc import Iterator, MutableMapping
from typing import Any

import pytest
import structlog
from httpx import AsyncClient
from structlog.testing import LogCapture

LogEntry = MutableMapping[str, Any]

EMAIL = "logging-user@example.com"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def log_output() -> Iterator[list[LogEntry]]:
    """Replace processors with a capturing one that still merges contextvars."""
    capture = LogCapture()
    original = structlog.get_config()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            capture,
        ]
    )
    try:
        yield capture.entries
    finally:
        structlog.configure(**original)


def _events_named(events: list[LogEntry], name: str) -> list[LogEntry]:
    return [e for e in events if e.get("event") == name]


@pytest.mark.asyncio
async def test_response_contains_generated_request_id(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert "x-request-id" in res.headers
    # UUID-ish — 36 chars with dashes.
    assert len(res.headers["x-request-id"]) >= 32


@pytest.mark.asyncio
async def test_response_honors_incoming_request_id(client: AsyncClient) -> None:
    provided = "11111111-2222-3333-4444-555555555555"
    res = await client.get("/api/v1/health", headers={"X-Request-ID": provided})
    assert res.headers["x-request-id"] == provided


@pytest.mark.asyncio
async def test_http_access_log_emitted(
    client: AsyncClient, log_output: list[LogEntry]
) -> None:
    await client.get("/api/v1/health")
    access_logs = _events_named(log_output, "http.request")
    assert access_logs, f"no http.request event in {log_output}"
    entry = access_logs[-1]
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/v1/health"
    assert entry["status"] == 200
    assert "duration_ms" in entry
    assert "request_id" in entry


@pytest.mark.asyncio
async def test_login_success_logged_with_user_id(
    client: AsyncClient, log_output: list[LogEntry]
) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "L"},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    events = _events_named(log_output, "auth.login.success")
    assert events, f"no auth.login.success in {log_output}"
    entry = events[-1]
    assert entry["user_id"] == user_id
    assert "request_id" in entry


@pytest.mark.asyncio
async def test_login_failure_logged(
    client: AsyncClient, log_output: list[LogEntry]
) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "L"},
    )
    await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-password"}
    )
    events = _events_named(log_output, "auth.login.failed")
    assert events, f"no auth.login.failed in {log_output}"
    assert events[-1]["email"] == EMAIL


@pytest.mark.asyncio
async def test_refresh_reuse_emits_security_event(
    client: AsyncClient, log_output: list[LogEntry]
) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "L"},
    )
    await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh is not None
    # Rotate once.
    await client.post("/api/v1/auth/refresh")
    # Replay the old token — must trigger reuse-detected security log.
    client.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
    await client.post("/api/v1/auth/refresh")

    events = _events_named(log_output, "auth.refresh.reuse_detected")
    assert events, f"no auth.refresh.reuse_detected in {log_output}"
    assert events[-1]["log_level"] in {"warning", "error"}
