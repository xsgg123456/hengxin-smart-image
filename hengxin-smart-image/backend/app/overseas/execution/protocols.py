"""Internal protocol registry. Missing business protocols fail closed."""
from typing import Protocol
from app.execution.events import EventSummary
from app.execution.workspace import Workspace
from .models import Job, KINDS


class Handler(Protocol):
    def prepare(self, job: Job, workspace: Workspace) -> str: ...
    def validate(self, job: Job, workspace: Workspace, summary: EventSummary) -> dict: ...
    # Optional callback called under the same lease fence/transaction as success.
    def publish(self, session, job: Job, result: dict) -> None: ...


_handlers: dict[str, Handler] = {}


def register(kind: str, handler: Handler):
    if kind not in KINDS:
        raise ValueError('Unknown overseas protocol')
    if kind in _handlers and _handlers[kind] is not handler:
        raise ValueError('Overseas protocol already registered')
    _handlers[kind] = handler


def resolve(kind: str) -> Handler:
    if kind not in _handlers:
        raise ValueError('Overseas protocol is not installed')
    return _handlers[kind]
