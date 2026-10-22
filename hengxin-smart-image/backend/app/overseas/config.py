"""Overseas settings reuse common validation without domestic environment fallback."""
from uuid import UUID
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings


class OverseasSettings(Settings):
    model_config = SettingsConfigDict(
        env_prefix='OVERSEAS_', env_file=None, extra='ignore', hide_input_in_errors=True,
    )

    database_url: str = Field(repr=False, min_length=1)
    redis_url: str = Field(repr=False, min_length=1)
    minio_endpoint: str = Field(min_length=1)
    minio_access_key: str = Field(repr=False, min_length=1)
    minio_secret_key: str = Field(repr=False, min_length=1)
    minio_bucket: str = Field(min_length=1)
    codex_execution_root: str = Field(min_length=1)
    skill_install_root: str = Field(min_length=1)
    local_skill_root: str = Field(min_length=1)
    generation_concurrency: int = Field(default=5, ge=1, le=5)
    db_application_name: str = Field(default='hx-overseas', pattern=r'^[a-z][a-z0-9-]{0,39}$')
    worker_node_name: str = 'overseas-worker-1'
    bootstrap_admin_corp_id: str = ''
    # Stable overseas member ID; unset means nobody can change availability.
    skill_toggle_owner_id: UUID | None = None
    bootstrap_admin_user_ids: str = Field(default='', repr=False)

    @field_validator('skill_toggle_owner_id', mode='before')
    @classmethod
    def optional_skill_owner(cls, value):
        return None if value == '' else value

    @field_validator(
        'database_url', 'redis_url', 'minio_endpoint', 'minio_access_key',
        'minio_secret_key', 'minio_bucket', 'codex_execution_root',
        'skill_install_root', 'local_skill_root',
    )
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Overseas resource configuration cannot be blank')
        return value


def load_overseas_settings() -> OverseasSettings:
    try:
        return OverseasSettings()
    except ValidationError as exc:
        # Never include input values or validator context in startup diagnostics.
        fields = sorted({'.'.join(map(str, error['loc'])) or 'configuration'
                         for error in exc.errors(include_input=False, include_context=False)})
        raise RuntimeError('Invalid OVERSEAS_ configuration: ' + ', '.join(fields)) from None
