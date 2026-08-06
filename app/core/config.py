"""Environment-backed application settings."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

type AppEnvironment = Literal["local", "test", "dev", "prod"]
type DatabaseUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class Settings(BaseSettings):
    """Validated runtime settings."""

    app_name: str = "Hotel Booking API"
    app_env: AppEnvironment = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: DatabaseUrl = (
        "postgresql+asyncpg://hotel_booking:hotel_booking_local@localhost:5432/"
        "hotel_booking"
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings instance per process."""

    return Settings()
