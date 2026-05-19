"""Shared test fixtures."""

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.rate_limit import limiter
from app.db.session import Base, engine
from app.main import app
from app.models import *  # noqa: F401, F403 — ensure models register on Base


@pytest.fixture(autouse=True)
def _disable_rate_limiting() -> Iterator[None]:
    """The in-memory rate limiter persists across tests; flip it off."""
    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture(autouse=True)
async def _reset_schema() -> AsyncIterator[None]:
    """Drop and recreate all tables before each test for isolation."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Truncate to keep the DB tidy between sessions; data already isolated above.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an async HTTP test client connected to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
