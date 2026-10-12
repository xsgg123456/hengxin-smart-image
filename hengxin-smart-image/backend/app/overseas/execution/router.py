from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.browser_auth import browser_request
from app.db.session import get_session
from app.overseas.auth.dependencies import CurrentMember
from app.overseas.tasks.queries import get_task
from app.overseas.permissions import principal_for, require_task_access
from . import cancel, events
from .models import Job

router = APIRouter(prefix='/api/overseas/v1', tags=['overseas-execution'])
Database = Annotated[Session, Depends(get_session)]


class CancelBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, strict=True)


def authorize(session, actor, task_id):
    task = get_task(session, task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)


@router.get('/tasks/{task_id}/jobs')
def jobs(task_id: UUID, actor: CurrentMember, session: Database):
    authorize(session, actor, task_id)
    rows = session.scalars(select(Job).where(Job.task_id == task_id).order_by(Job.created_at, Job.id))
    return {'items': [events.serialize(row) for row in rows]}


@router.get('/tasks/{task_id}/execution-events')
def execution_events(task_id: UUID, actor: CurrentMember, session: Database, after: int = Query(0, ge=0)):
    authorize(session, actor, task_id)
    return events.read(session, task_id, after)


@router.post('/jobs/{job_id}/cancel', dependencies=[Depends(browser_request)])
def stop(job_id: UUID, body: CancelBody, actor: CurrentMember, session: Database):
    return cancel.cancel(session, actor, job_id, body.version)
