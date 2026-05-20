"""Pydantic schemas for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, field_validator


def _normalize_email(value: str) -> str:
    """Treat email addresses case-insensitively at the auth boundary.

    Without this, `Foo@bar.com` and `foo@bar.com` register as separate
    accounts even though every mainstream mail provider treats them as
    one mailbox — silent account-takeover ambiguity.
    """
    return value.strip().lower()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    """Login / refresh response — refresh token is delivered via HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return _normalize_email(v)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return _normalize_email(v)
