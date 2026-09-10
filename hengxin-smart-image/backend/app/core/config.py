from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    enable_test_jobs: bool = False
    enable_fixture_executor: bool = False
    enable_codex_executor: bool = False
    codex_binary: str = ''
    codex_bwrap_binary: str = '/opt/hengxin-runtime/bwrap'
    codex_auth_file: str = Field(default='', repr=False)
    codex_execution_root: str = '/var/lib/hengxin/execution'
    codex_version: str = '0.153.4'
    codex_timeout_seconds: int = Field(default=3600, ge=10, le=3600)
    queue_visibility_seconds: int = Field(default=4200, ge=60, le=86400)
    generation_concurrency: int = Field(default=1, ge=1, le=10)
    fixture_delay_seconds: int = Field(default=3, ge=0, le=60)
    skill_install_root: str = '/var/lib/hengxin/skills'
    worker_node_name: str = 'worker-1'
    job_lease_seconds: int = Field(default=30, ge=10, le=300)
    job_heartbeat_seconds: int = Field(default=5, ge=1, le=60)
    enable_dev_identity: bool = False
    dev_user_id: UUID = UUID('00000000-0000-4000-8000-000000000001')
    dev_user_name: str = '本地联调用户'
    dev_user_role: Literal['super_admin', 'design_manager', 'designer', 'operator'] = 'operator'
    database_url: str = Field(repr=False, min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = Field(repr=False, min_length=1)
    minio_secret_key: str = Field(repr=False, min_length=1)
    minio_secure: bool = False
    minio_bucket: str = 'hengxin-smart-image'
    outbox_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    outbox_redispatch_seconds: int = Field(default=30, ge=1, le=3600)

    @model_validator(mode="after")
    def validate_environment(self):
        if self.enable_codex_executor:
            if self.enable_fixture_executor:
                raise ValueError('Choose only one generation executor')
            if not self.codex_binary or not self.codex_auth_file:
                raise ValueError('Codex binary and auth file are required')
            if self.queue_visibility_seconds < self.codex_timeout_seconds + 600:
                raise ValueError('Queue visibility must exceed execution timeout by 600 seconds')
        if self.enable_fixture_executor and self.app_env != 'test':
            raise ValueError('ENABLE_FIXTURE_EXECUTOR is allowed only in test')
        if self.job_heartbeat_seconds * 2 >= self.job_lease_seconds:
            raise ValueError('Job heartbeat must be less than half the lease')
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.app_env == "production" and self.enable_test_jobs:
            raise ValueError("ENABLE_TEST_JOBS is forbidden in production")
        if self.app_env == 'production' and self.enable_dev_identity:
            raise ValueError('ENABLE_DEV_IDENTITY is forbidden in production')
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
