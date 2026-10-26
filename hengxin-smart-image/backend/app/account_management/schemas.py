"""Public account-management contract; never serialize credential payloads."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class StartInput(Input):
    intent: Literal['connect', 'renew', 'replace']
    revision: int = Field(ge=0)


class ActivateInput(Input):
    acknowledged: bool


class RemoveInput(Input):
    revision: int = Field(ge=0)


class PublicModel(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)


class Audit(PublicModel):
    time: str
    operator: str
    action: str
    result: str


class Account(PublicModel):
    status: Literal['empty', 'unchecked', 'ready', 'expired', 'network']
    email: str
    workspace: str
    checked: str
    updated: str
    audit: list[Audit]
    revision: int = Field(ge=0)
    checking: bool


class Authorization(PublicModel):
    id: str
    step: Literal['starting', 'waiting', 'checking', 'expired', 'failed', 'mismatch', 'verified']
    userCode: str
    verificationUrl: str
    expiresAt: int | float
    candidateEmail: str
    candidateWorkspace: str
    different: bool
    message: str


class Cancelled(PublicModel):
    ok: Literal[True]
