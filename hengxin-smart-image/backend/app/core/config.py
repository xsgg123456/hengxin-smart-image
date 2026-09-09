from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    enable_test_jobs: bool = False
    database_url: str = Field(repr=False, min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = Field(repr=False, min_length=1)
    minio_secret_key: str = Field(repr=False, min_length=1)
    minio_secure: bool = False
    outbox_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    outbox_redispatch_seconds: int = Field(default=30, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_environment(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.app_env == "production" and self.enable_test_jobs:
            raise ValueError("ENABLE_TEST_JOBS is forbidden in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
