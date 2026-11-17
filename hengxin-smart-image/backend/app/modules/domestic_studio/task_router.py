"""Member task lifecycle, plus read-only super-admin task observation."""
from uuid import UUID
from fastapi import APIRouter, Query, Response

from . import admin_queries, task_deletion, task_queries, task_service
from .admin_router import Admin, audit
from .router import Database, Key, User, WRITE
from .task_models import Task
from .task_schemas import DeleteTask, NewTask, TaskStatus, UpdateTask, WorkspaceName

router = APIRouter(prefix='/domestic-studio/tasks', tags=['domestic-tasks'])
admin_router = APIRouter(prefix='/management/domestic-studio/tasks', tags=['domestic-tasks-admin'])


@router.get('')
def listing(actor: User, session: Database, workspace: WorkspaceName,
            status: TaskStatus | None = None, search: str = Query('', max_length=200),
            page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    return task_queries.listing(session, owner_id=actor.id, workspace=workspace, status=status,
                                search=search, page=page, page_size=pageSize)


@router.post('', dependencies=WRITE)
def create(body: NewTask, actor: User, session: Database, key: Key):
    row = task_service.create(session, actor.id, body, key)
    result = task_queries.detail(session, row.id)
    session.commit()
    return result


@router.get('/{task_id}')
def detail(task_id: UUID, actor: User, session: Database):
    task_service.owned(session, actor.id, task_id)
    return task_queries.detail(session, task_id)


@router.patch('/{task_id}', dependencies=WRITE)
def update(task_id: UUID, body: UpdateTask, actor: User, session: Database, key: Key):
    row = task_service.update(session, actor.id, task_id, body, key)
    result = task_queries.detail(session, row.id)
    session.commit()
    return result


@router.delete('/{task_id}', dependencies=WRITE)
def delete(task_id: UUID, body: DeleteTask, actor: User, session: Database):
    result = task_deletion.request(session, actor.id, task_id, body.version)
    session.commit()
    return result


@router.get('/{task_id}/deletion')
def deletion(task_id: UUID, actor: User, session: Database):
    row = task_service.owned(session, actor.id, task_id, include_deleted=True)
    return task_deletion.dto(session, row)


@admin_router.get('')
def admin_listing(actor: Admin, session: Database, response: Response, ownerId: UUID | None = None,
                  workspace: WorkspaceName | None = None, status: TaskStatus | None = None,
                  search: str = Query('', max_length=200), page: int = Query(1, ge=1),
                  pageSize: int = Query(20, ge=1, le=100)):
    result = task_queries.listing(session, owner_id=ownerId, workspace=workspace, status=status,
                                 search=search, page=page, page_size=pageSize, members=True)
    audit(session, actor, actor.id, 'studio_task_list', ownerId=str(ownerId) if ownerId else None,
          workspace=workspace, status=status, page=page, pageSize=pageSize)
    response.headers['Cache-Control'] = 'private, no-store'
    return result


@admin_router.get('/{task_id}')
def admin_detail(task_id: UUID, actor: Admin, session: Database, response: Response):
    from fastapi import HTTPException
    row = session.get(Task, task_id)
    if row is None or row.deletion_status == 'deleted':
        raise HTTPException(404, '任务不存在或已删除')
    result = dict(task=task_queries.detail(session, task_id),
                  sessions=admin_queries.siblings(session, row.owner_id, task_id=row.id))
    audit(session, actor, row.owner_id, 'studio_task_view', taskId=str(row.id))
    response.headers['Cache-Control'] = 'private, no-store'
    return result
