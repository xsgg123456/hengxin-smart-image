from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ApplicationStatus = Literal['pending', 'approved', 'rejected', 'withdrawn']
Directory = Literal['members', 'legacy']


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject']
    role: str | None = Field(default=None, max_length=32)
    version: int = Field(ge=1, strict=True)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode='after')
    def approval_requires_role(self):
        self.reason = self.reason.strip() if self.reason else None
        if self.decision == 'approve' and not self.role:
            raise ValueError('批准申请必须选择本业务角色')
        if self.decision == 'reject' and self.role is not None:
            raise ValueError('拒绝申请不能分配角色')
        if self.decision == 'reject' and not self.reason:
            raise ValueError('拒绝申请必须填写原因')
        return self
