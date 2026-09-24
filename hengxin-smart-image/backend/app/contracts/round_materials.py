from pydantic import BaseModel
from .business import Picture
from .fields import omitted


class MaterialPrompt(BaseModel):
    label: str
    text: str


class MaterialToolCall(BaseModel):
    label: str
    prompt: str
    images: list[str]


class MaterialPicture(BaseModel):
    role: str
    label: str
    picture: Picture | None
    version: int = omitted()
    reason: str = omitted()


class RoundMaterials(BaseModel):
    taskId: str
    roundId: str
    note: str
    status: str
    systemPrompts: list[MaterialPrompt]
    toolCalls: list[MaterialToolCall]
    inputs: list[MaterialPicture]
    outputs: list[MaterialPicture]
    notices: list[str]
