from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Header
from app.contracts import business as b
from app.modules.tasks.router import Database, SharedUser
from app.modules.tasks.service import accept_round

router = APIRouter(tags=['revisions'])


@router.post('/tasks/{id}/rounds', response_model=b.Accepted, status_code=202)
def revise(id: UUID, body: b.RevisionInput, user: SharedUser, session: Database,
           idempotency_key: Annotated[str, Header(min_length=1, max_length=128)]):
    return accept_round(session, user, id, body, idempotency_key)
