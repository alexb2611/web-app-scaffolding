"""JWT token and password hashing utilities."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    encoded: str = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded


@dataclass(frozen=True)
class RefreshTokenIssued:
    """A freshly minted refresh token plus the metadata to store server-side."""

    token: str
    jti: str
    issued_at: datetime
    expires_at: datetime


def create_refresh_token(subject: str) -> RefreshTokenIssued:
    """Mint a refresh JWT with a unique `jti` and return the storage metadata."""
    jti = str(uuid.uuid4())
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(days=settings.refresh_token_expire_days)
    encoded: str = jwt.encode(
        {
            "sub": subject,
            "exp": expires_at,
            "iat": issued_at,
            "jti": jti,
            "type": "refresh",
        },
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return RefreshTokenIssued(
        token=encoded, jti=jti, issued_at=issued_at, expires_at=expires_at
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    payload: dict[str, Any] = jwt.decode(
        token, settings.secret_key, algorithms=[settings.algorithm]
    )
    return payload


__all__ = [
    "JWTError",
    "RefreshTokenIssued",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_password_hash",
    "verify_password",
]
