"""Refresh token lifecycle: issue, rotate, revoke, family-revoke."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import RefreshTokenIssued, create_refresh_token
from app.models.refresh_token import RefreshToken
from app.models.user import User


@dataclass(frozen=True)
class IssuedToken:
    """Newly issued refresh token plus the persisted row id."""

    record_id: str
    token: str


@dataclass(frozen=True)
class RotateResult:
    """Outcome of a rotate() call.

    `new` is populated on success. `reuse_detected` is True when the caller
    presented a token whose row was already revoked or rotated — in that
    case the entire family has been revoked as a side effect and the
    caller should log a security event.
    """

    new: IssuedToken | None = None
    reuse_detected: bool = False


async def issue_for_user(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> IssuedToken:
    """Mint a fresh refresh token and persist its server-side state."""
    minted: RefreshTokenIssued = create_refresh_token(user.email)
    row = RefreshToken(
        user_id=user.id,
        jti=minted.jti,
        issued_at=minted.issued_at,
        expires_at=minted.expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(row)
    await db.flush()
    return IssuedToken(record_id=row.id, token=minted.token)


async def _get_by_jti(db: AsyncSession, jti: str) -> RefreshToken | None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    return result.scalar_one_or_none()


async def rotate(
    db: AsyncSession,
    *,
    presented_jti: str,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> RotateResult:
    """Rotate a refresh token.

    On success returns a `RotateResult` with `.new` populated. On reuse
    (token was already rotated or revoked) returns a result with
    `reuse_detected=True` and revokes the entire family as a side effect.
    On any other failure returns an empty result.
    """
    row = await _get_by_jti(db, presented_jti)
    if row is None or row.user_id != user.id:
        return RotateResult()

    now = datetime.now(UTC)
    if row.expires_at <= now:
        return RotateResult()

    if row.revoked_at is not None or row.replaced_by_id is not None:
        await revoke_family(db, jti=row.jti)
        return RotateResult(reuse_detected=True)

    new = await issue_for_user(db, user, user_agent=user_agent, ip_address=ip_address)
    row.revoked_at = now
    row.replaced_by_id = new.record_id
    await db.flush()
    return RotateResult(new=new)


async def revoke_family(db: AsyncSession, *, jti: str) -> None:
    """Revoke every token in the chain that contains `jti`.

    Walks both predecessors (rows that point at us via `replaced_by_id`,
    transitively) and successors (rows we point at, transitively).
    """
    seed = await _get_by_jti(db, jti)
    if seed is None:
        return
    family_ids = await _collect_family_ids(db, seed.id)
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.id.in_(family_ids),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await db.flush()


async def _collect_family_ids(db: AsyncSession, seed_id: str) -> set[str]:
    """Return all row ids reachable from `seed_id` via the chain links."""
    visited: set[str] = {seed_id}
    frontier: set[str] = {seed_id}
    while frontier:
        result = await db.execute(
            select(RefreshToken.id, RefreshToken.replaced_by_id).where(
                or_(
                    RefreshToken.id.in_(frontier),
                    RefreshToken.replaced_by_id.in_(frontier),
                )
            )
        )
        new_ids: set[str] = set()
        for row_id, replaced_by_id in result.all():
            if row_id and row_id not in visited:
                new_ids.add(row_id)
            if replaced_by_id and replaced_by_id not in visited:
                new_ids.add(replaced_by_id)
        visited |= new_ids
        frontier = new_ids
    return visited


async def revoke(db: AsyncSession, *, jti: str) -> None:
    """Revoke a single token row (used by /logout)."""
    row = await _get_by_jti(db, jti)
    if row is None or row.revoked_at is not None:
        return
    row.revoked_at = datetime.now(UTC)
    await db.flush()


async def is_active(db: AsyncSession, *, jti: str) -> bool:
    """True iff the token row exists, isn't revoked, and hasn't been rotated."""
    row = await _get_by_jti(db, jti)
    if row is None:
        return False
    if row.revoked_at is not None or row.replaced_by_id is not None:
        return False
    return row.expires_at > datetime.now(UTC)
