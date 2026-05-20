"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version as _pkg_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.observability import configure_observability
from app.core.rate_limit import limiter
from app.db.session import engine

# Read the version from the installed package metadata so the
# OpenAPI contract's `info.version` always tracks pyproject.toml.
# CI fails any PR that changes the OpenAPI schema without also
# bumping this value — see `.github/workflows/ci.yml`.
__version__ = _pkg_version("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle hook."""
    # Startup: you could run migrations or warm caches here.
    yield
    # Shutdown: dispose of the connection pool.
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url="/api/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded, _rate_limit_exceeded_handler  # type: ignore[arg-type]
    )

    # CORS — applied first via add_middleware so it wraps outside the
    # request-context middleware (allowed-origins handling for preflight).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Request context + access logging. Added after CORS so it sits inside
    # the CORS layer — request_id is bound for the actual handler.
    app.add_middleware(RequestContextMiddleware)

    # Routes
    app.include_router(v1_router)

    # Observability: OpenTelemetry + Sentry. Both opt-in via env. Called
    # after middleware + routes so FastAPI instrumentation can see the
    # final route table.
    configure_observability(app)

    return app


app = create_app()
