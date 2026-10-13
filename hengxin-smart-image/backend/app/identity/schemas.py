"""Validate identity boundaries before persisting or trusting remote grants."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from app.identity.tokens import is_expired

TicketPurpose = Literal['access', 'session', 'application']


class Member(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    corp_id: str = Field(min_length=1, max_length=200)
    provider_user_id: str = Field(min_length=1, max_length=200)
    union_id: str | None = Field(max_length=200)
    name: str = Field(min_length=1, max_length=200)
    department: str = Field(max_length=200)

    @field_validator('corp_id', 'provider_user_id', 'name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('identity field must not be blank')
        return value


class IdentityGrant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    member: Member
    identity_session_id: str = Field(min_length=1, max_length=128, strict=True)
    expires_at: AwareDatetime

    @field_validator('expires_at')
    @classmethod
    def future_expiry(cls, value):
        if is_expired(value):
            raise ValueError('identity expiry must be in the future')
        return value
