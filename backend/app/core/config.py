"""Core application configuration loaded from environment variables."""

from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings

PLACEHOLDER_SECRET_KEY = "change-me-to-a-random-secret-key"


class Settings(BaseSettings):
    """Application settings.

    All values can be overridden via environment variables.
    See .env.example at the project root for available options.
    """

    # General
    app_name: str = "myapp"
    environment: str = "development"
    debug: bool = False

    # Security
    secret_key: str = PLACEHOLDER_SECRET_KEY
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Refresh-token cookie.
    # `cookie_secure` must be True in any deployment served over HTTPS — the
    # default flips on automatically when `environment` is "production".
    refresh_cookie_name: str = "refresh_token"
    auth_present_cookie_name: str = "auth_present"
    cookie_path: str = "/api/v1/auth"
    cookie_samesite: str = "lax"  # "lax" | "strict" | "none"
    cookie_domain: str | None = None
    cookie_secure: bool | None = None  # None = auto from environment

    @property
    def cookie_secure_resolved(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"

    # CORS (comma-separated string, parsed via property)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Rate limiting. On by default; set RATE_LIMIT_ENABLED=false for E2E suites
    # and load tests that would otherwise trip the auth-endpoint throttles.
    rate_limit_enabled: bool = True

    # ── Observability ───────────────────────────────────────────────────
    # OpenTelemetry. The exporter only sends to a backend when an endpoint
    # is configured; otherwise instrumentation is loaded but spans are
    # silently dropped. `otel_console_exporter` adds a stdout span exporter
    # for local development — useful for seeing the trace tree without a
    # running Tempo/Jaeger.
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str | None = None  # defaults to app_name at boot
    otel_console_exporter: bool = False

    # Sentry. SDK only initialises if a DSN is set, so this is opt-in.
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0  # 0.0 = errors only, no perf data
    sentry_send_default_pii: bool = False  # opt-in only — names/emails/IPs

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/myapp"

    # For Alembic (sync driver)
    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _reject_placeholder_secret_in_production(self) -> Self:
        if (
            self.environment == "production"
            and self.secret_key == PLACEHOLDER_SECRET_KEY
        ):
            raise ValueError(
                "secret_key is still the .env.example placeholder. "
                "Set SECRET_KEY to a strong random value before running in production."
            )
        return self


settings = Settings()
