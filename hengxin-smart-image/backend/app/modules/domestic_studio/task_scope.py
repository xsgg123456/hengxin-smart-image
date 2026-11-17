"""Resolve a real task once per request and project task-scoped Studio URLs."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_session
from app.modules.auth.permissions import require_permission
from . import task_service
from .task_models import Task


def resolve(request: Request, actor=Depends(require_permission('shared_resources')),
            session: Session = Depends(get_session)):
    identity = request.path_params.get('task_id')
    if identity is None:
        return request.path_params['workspace']
    try:
        identity = UUID(str(identity))
    except ValueError:
        raise HTTPException(422, '任务编号无效') from None
    task = task_service.owned(session, actor.id, identity)
    session.info['domestic_task_id'] = task.id
    if request.method not in ('GET', 'HEAD'):
        task_service.writable(task)
    return task.workspace


Scope = Annotated[str, Depends(resolve)]


def urls(value, workspace, task_id):
    old = f'/api/v1/domestic-studio/workspaces/{workspace}/'
    new = f'/api/v1/domestic-studio/tasks/{task_id}/studio/'
    if isinstance(value, dict):
        return {key: (new + item[len(old):] if key == 'url' and isinstance(item, str) and item.startswith(old)
                      else urls(item, workspace, task_id)) for key, item in value.items()}
    if isinstance(value, list):
        return [urls(item, workspace, task_id) for item in value]
    return value


def project_view(session, result, channel):
    identity = session.info.get('domestic_task_id') or (channel.task_id if channel else None)
    if identity is None:
        return result
    task = session.get(Task, identity)
    result.update(taskId=str(task.id), taskVersion=result['taskVersion'] + task.version,
                  completed=task.completed)
    return urls(result, task.workspace, task.id)
