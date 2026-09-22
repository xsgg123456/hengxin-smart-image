"""API image channel settings, deliberately independent of Codex execution settings."""
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PARAMETERS = {
    'model': 'gpt-image-2.5-sunburst', 'size': '1024x1024',
    'resolution': '1K', 'quality': 'xhigh', 'n': 1,
}


class ApiImageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_prefix='API_IMAGE_', extra='ignore', hide_input_in_errors=True)
    enabled: bool = False
    api_key: SecretStr = Field(default=SecretStr(''), repr=False)
    base_url: str = 'https://api.qhhengxin.top'
    request_timeout_seconds: int = Field(default=180, ge=10, le=600)
    download_timeout_seconds: int = Field(default=60, ge=5, le=180)
    max_download_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=30 * 1024 * 1024)
    allowed_result_hosts: list[str] = Field(default_factory=lambda: ['cdn3.dmiapi.com'])
    broker_url: str = Field(default='redis://localhost:6379/1', repr=False)
    lease_seconds: int = Field(default=360, ge=60, le=1800)

    @field_validator('base_url')
    @classmethod
    def secure_endpoint(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('API image base URL must be an HTTPS origin without credentials')
        return value.rstrip('/')

    @field_validator('allowed_result_hosts')
    @classmethod
    def exact_hosts(cls, values):
        if not values or any(not host or '/' in host or ':' in host or '*' in host
                             or '@' in host for host in values):
            raise ValueError('Result hosts must be explicit DNS hostnames')
        return [host.lower().rstrip('.') for host in values]

    @model_validator(mode='after')
    def adequate_lease(self):
        if self.lease_seconds < self.request_timeout_seconds + self.download_timeout_seconds + 60:
            raise ValueError('API image lease must exceed request and download deadlines by 60 seconds')
        return self


@lru_cache
def get_api_settings():
    return ApiImageSettings()
