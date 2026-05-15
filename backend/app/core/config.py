"""Core application configuration loaded from environment variables."""

from pydantic import model_validator
from pydantic_settings import BaseSettings

PLACEHOLDER_SECRET_KEY = "change-me-to-a-random-secret-key"  # noqa: S105


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

    # CORS (comma-separated string, parsed via property)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/myapp"

    # For Alembic (sync driver)
    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _reject_placeholder_secret_in_prod(self) -> "Settings":
        is_prod = self.environment == "production"
        if is_prod and self.secret_key == PLACEHOLDER_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a high-entropy value when "
                "ENVIRONMENT=production (still using the .env.example placeholder)."
            )
        return self


settings = Settings()
