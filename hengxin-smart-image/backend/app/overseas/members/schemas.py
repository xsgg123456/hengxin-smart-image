from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.overseas.auth.models import ROLES

Role = Literal['designer', 'design_manager', 'super_admin']
Status = Literal['active', 'pending', 'disabled']


class MemberPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    roles: list[Role] = Field(max_length=1)
    status: Literal['active', 'disabled']
    version: int = Field(ge=1, strict=True)
    feedbackManage: bool | None = Field(default=None, strict=True)

    @field_validator('roles')
    @classmethod
    def unique_roles(cls, values):
        return sorted(set(values), key=ROLES.index)

    @model_validator(mode='after')
    def active_has_role(self):
        if self.status == 'active' and not self.roles:
            raise ValueError('启用成员必须且只能有一个角色')
        if self.feedbackManage and (self.status != 'active' or self.roles == ['designer']):
            raise ValueError('仅可授予已启用的管理员反馈管理权限')
        return self
