"""Authentication endpoints: register, login, refresh, logout, profile.

Refresh tokens live in an HttpOnly cookie scoped to `/api/v1/auth` and are
never returned in a response body. A separate non-sensitive `auth_present`
cookie tells the frontend middleware whether to redirect — it carries no
credential value and is safe to read from JS.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.core.security import (
    JWTError,
    create_access_token,
    decode_token,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services import refresh_token_service
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_log = get_logger("auth")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure_resolved,
        httponly=True,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )
    response.set_cookie(
        key=settings.auth_present_cookie_name,
        value="1",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure_resolved,
        httponly=False,  # Read by Next.js middleware for redirect logic.
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.cookie_path,
        domain=settings.cookie_domain,
    )
    response.delete_cookie(
        key=settings.auth_present_cookie_name,
        path="/",
        domain=settings.cookie_domain,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Create a new user account."""
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    user = await create_user(db, data)
    _log.info("auth.register.success", user_id=user.id, email=user.email)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate and issue an access token + refresh cookie."""
    user = await authenticate_user(db, data.email, data.password)
    if user is None:
        _log.info("auth.login.failed", email=data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    issued = await refresh_token_service.issue_for_user(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, issued.token)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    _log.info("auth.login.success", user_id=user.id)
    return TokenResponse(access_token=create_access_token(user.email))


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate the refresh-token cookie and return a new access token."""
    cookie_token = request.cookies.get(settings.refresh_cookie_name)
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    try:
        payload = decode_token(cookie_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        jti = payload.get("jti")
        email = payload.get("sub")
        if not jti or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed refresh token",
            )
    except JWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from err

    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    result = await refresh_token_service.rotate(
        db,
        presented_jti=jti,
        user=user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    if result.new is None:
        # Commit explicitly: get_db will roll back on HTTPException and we
        # need the family-revocation side effect to persist.
        await db.commit()
        _clear_auth_cookies(response)
        if result.reuse_detected:
            _log.warning("auth.refresh.reuse_detected", user_id=user.id, jti=jti)
        else:
            _log.info("auth.refresh.invalid", email=email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid",
        )

    _set_refresh_cookie(response, result.new.token)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    _log.info("auth.refresh.success", user_id=user.id)
    return TokenResponse(access_token=create_access_token(user.email))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke the current refresh token chain and clear cookies."""
    cookie_token = request.cookies.get(settings.refresh_cookie_name)
    revoked_jti: str | None = None
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            jti = payload.get("jti")
            if isinstance(jti, str):
                await refresh_token_service.revoke_family(db, jti=jti)
                revoked_jti = jti
        except JWTError:
            # Even an invalid token gets the cookies cleared below.
            pass
    _clear_auth_cookies(response)
    _log.info("auth.logout.success", jti=revoked_jti)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""
    return current_user
