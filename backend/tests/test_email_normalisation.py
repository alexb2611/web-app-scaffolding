"""Email addresses must be treated case-insensitively at the auth boundary.

`Foo@bar.com` and `foo@bar.com` are the same mailbox per RFC 5321 §2.4
(the local part is technically case-sensitive but every mainstream
provider normalises it). Letting them register as separate accounts
silently creates account-takeover ambiguity.
"""

import pytest
from httpx import AsyncClient

PASSWORD = "correct-horse-battery-staple"


@pytest.mark.asyncio
async def test_register_lowercases_email(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "Foo@Bar.com", "password": PASSWORD},
    )
    assert res.status_code == 201, res.text
    assert res.json()["email"] == "foo@bar.com"


@pytest.mark.asyncio
async def test_duplicate_email_different_case_is_rejected(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "Foo@bar.com", "password": PASSWORD},
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "foo@bar.com", "password": PASSWORD},
    )
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_login_is_case_insensitive(client: AsyncClient) -> None:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "Foo@bar.com", "password": PASSWORD},
    )
    assert reg.status_code == 201, reg.text

    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "FOO@BAR.COM", "password": PASSWORD},
    )
    assert res.status_code == 200, res.text
