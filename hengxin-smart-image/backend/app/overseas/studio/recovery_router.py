"""Conversation-scoped manual original-file receipt API."""
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from app.core.browser_auth import browser_request
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.router import Database
from . import queries, recovery_transport
from .recovery_transport import Selection

router = APIRouter()


class RecoverFiles(BaseModel):
    model_config = ConfigDict(extra='forbid')
    files: list[Selection] = Field(min_length=1, max_length=100)


def native_request(session, actor, task_id, conversation_id, operation, files=()):
    actor_id = actor.id
    try:
        task = queries.access(session, actor, task_id, write=True)
        queries.conversation(session, task.id, conversation_id, writable=True)
    finally:
        # Native recovery locks this task again. Release API/auth locks before waiting.
        session.rollback()
    return recovery_transport.request(operation, actor_id, task_id, conversation_id, files)


@router.get('/conversations/{conversation_id}/recoverable-files')
def available(task_id: UUID, conversation_id: UUID, actor: CurrentMember, session: Database):
    return native_request(session, actor, task_id, conversation_id, 'available')


@router.post('/conversations/{conversation_id}/recover-files', dependencies=[Depends(browser_request)])
def receive(task_id: UUID, conversation_id: UUID, body: RecoverFiles, actor: CurrentMember,
            session: Database):
    return native_request(session, actor, task_id, conversation_id, 'receive', body.files)
