"""Independent identity process configuration: no business environment files."""
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IdentitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='IDENTITY_', env_file=None, extra='ignore',
                                      hide_input_in_errors=True)
    redis_url: str = Field(repr=False)
    public_origin: str
    domestic_service_key: str = Field(min_length=32, repr=False)
    overseas_service_key: str = Field(min_length=32, repr=False)
    dingtalk_corp_id: str = ''
    dingtalk_client_id: str = ''
    dingtalk_agent_id: str = ''
    dingtalk_client_secret: str = Field(default='', repr=False)
    dingtalk_api_base_url: str = 'https://api.dingtalk.com'
    session_ttl_seconds: int = Field(default=28800, ge=60, le=604800)

    @property
    def dingtalk_callback_domain(self):
        return self.public_origin

    @model_validator(mode='after')
    def validate_configuration(self):
        origin = urlsplit(self.public_origin)
        if (origin.scheme not in ('http', 'https') or not origin.hostname or
                origin.username or origin.password or origin.query or origin.fragment or
                origin.path not in ('', '/')):
            raise ValueError('identity public_origin must be an HTTP origin')
        keys = (self.domestic_service_key, self.overseas_service_key)
        if keys[0] == keys[1] or any(len(set(key)) < 12 or not key.isascii() or
                                     any(c.isspace() for c in key) for key in keys):
            raise ValueError('identity service keys must be strong, independent ASCII values')
        if urlsplit(self.redis_url).scheme not in ('redis', 'rediss'):
            raise ValueError('identity redis_url must use Redis')
        return self
