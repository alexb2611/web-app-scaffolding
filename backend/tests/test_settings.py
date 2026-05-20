"""Production-environment guard rails on `Settings`.

The default `secret_key` is a placeholder shipped in `.env.example` so
local dev "just works". Deploying that to production silently would let
anyone with the public string forge JWTs. Settings must refuse to load
production when the placeholder is still in place.
"""

import pytest
from pydantic import ValidationError

from app.core.config import PLACEHOLDER_SECRET_KEY, Settings


def test_production_with_placeholder_secret_key_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(environment="production", secret_key=PLACEHOLDER_SECRET_KEY)
    assert "secret_key" in str(exc.value).lower()


def test_production_with_strong_secret_key_is_ok() -> None:
    s = Settings(environment="production", secret_key="a" * 64)
    assert s.environment == "production"


def test_development_with_placeholder_secret_key_is_ok() -> None:
    """Dev should still boot with the placeholder so `cp .env.example .env` works."""
    s = Settings(environment="development", secret_key=PLACEHOLDER_SECRET_KEY)
    assert s.environment == "development"
