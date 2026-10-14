"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # === Application ===
    APP_NAME: str = "MedBook API"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # === Security / JWT ===
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # === Database ===
    POSTGRES_USER: str = "medbook"
    POSTGRES_PASSWORD: str = "medbook"
    POSTGRES_DB: str = "medbook"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # === Redis ===
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # === Cache ===
    CACHE_TTL_DOCTORS: int = 300
    CACHE_TTL_DOCTOR: int = 300
    CACHE_TTL_SLOTS: int = 60

    # === Rate limiting ===
    RATE_LIMIT_AUTH: str = "5/60"
    RATE_LIMIT_APPOINTMENTS: str = "10/60"

    # === Business rules ===
    CANCELLATION_MIN_HOURS: int = 2
    MAX_ACTIVE_APPOINTMENTS: int = 5

    # === CORS ===
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @computed_field
    @property
    def database_url(self) -> str:
        """Build async PostgreSQL connection URL from parts."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        """Build Redis connection URL from parts."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()
