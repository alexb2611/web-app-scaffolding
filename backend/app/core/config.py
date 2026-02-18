"""Core application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


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
    secret_key: str = "change-me-to-a-random-secret-key"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # CORS (comma-separated string, parsed via property)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@db:5432/myapp"
    )

    # For Alembic (sync driver)
    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
