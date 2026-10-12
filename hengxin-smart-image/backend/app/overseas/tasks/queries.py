from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from app.overseas.auth.models import Member, MemberRole
from app.overseas.members.service import roles_for
from app.overseas.permissions import can_access_task, principal_for, require_task_access, scopes, task_filter
from .models import Task, TaskEvent, TaskSku

DESIGN_ROLES = ('designer', 'design_manager')


def eligible(session, member):
    return member.status == 'active' and bool(set(roles_for(session, member.id)) & set(DESIGN_ROLES))


def get_task(session, task_id, lock=False):
    query = select(Task).where(Task.id == task_id).execution_options(populate_existing=True)
    task = session.scalar(query.with_for_update() if lock else query)
    if task is None:
        raise HTTPException(404, '海外任务不存在')
    return task


def summary(session, task, principal):
    creator = session.get(Member, task.created_by)
    designer = session.get(Member, task.designer_id)
    skus = session.scalars(select(TaskSku).where(TaskSku.task_id == task.id).order_by(TaskSku.position))
    return {'id': str(task.id), 'name': task.name, 'productName': task.product_name,
            'brand': task.brand, 'platform': task.platform, 'market': task.market,
            'remarks': task.remarks, 'skus': [{'code': item.code} for item in skus],
            'status': task.status, 'version': task.version, 'createdAt': task.created_at,
            'updatedAt': task.updated_at, 'createdBy': {'id': str(creator.id), 'name': creator.name},
            'designer': {'id': str(designer.id), 'name': designer.name,
                         'status': designer.status, 'eligible': eligible(session, designer)},
            'capabilities': [permission for permission in ('task.read', 'task.design', 'task.reassign')
                             if can_access_task(principal, task.created_by, task.designer_id, permission)]}


def detail(session, task_id, actor, lock=False):
    task = get_task(session, task_id, lock)
    principal = principal_for(session, actor)
    require_task_access(principal, task.created_by, task.designer_id)
    result = summary(session, task, principal)
    events = session.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id).order_by(TaskEvent.version))
    result['events'] = [{'id': str(item.id), 'kind': item.kind, 'actorId': str(item.actor_id),
                         'actorName': item.actor_name, 'title': item.title, 'at': item.created_at,
                         'beforeDesignerId': str(item.before_designer_id) if item.before_designer_id else None,
                         'afterDesignerId': str(item.after_designer_id), 'version': item.version}
                        for item in events]
    return result


def list_tasks(session, actor, search='', scope='all', status=None, page=1, page_size=20):
    principal = principal_for(session, actor)
    filters = [task_filter(principal, Task.created_by, Task.designer_id)]
    if scope == 'mine':
        filters.append(or_(Task.created_by == actor.id, Task.designer_id == actor.id))
    if status:
        filters.append(Task.status == status)
    if search:
        terms = [column.icontains(search, autoescape=True) for column in (Task.name, Task.product_name, Task.brand)]
        terms.append(select(TaskSku.id).where(TaskSku.task_id == Task.id,
                     TaskSku.code.icontains(search, autoescape=True)).exists())
        try:
            terms.append(Task.id == UUID(search))
        except ValueError:
            pass
        filters.append(or_(*terms))
    total = session.scalar(select(func.count()).select_from(Task).where(*filters))
    records = session.scalars(select(Task).where(*filters).order_by(Task.created_at.desc(), Task.id)
                             .offset((page - 1) * page_size).limit(page_size))
    return {'items': [summary(session, task, principal) for task in records], 'total': total,
            'page': page, 'pageSize': page_size}


def designers(session, actor, search='', page=1, page_size=20):
    roles = principal_for(session, actor).roles
    if not (scopes(roles, 'task.create') or scopes(roles, 'task.reassign')):
        raise HTTPException(403, '没有选择设计成员的权限')
    filters = [Member.status == 'active', select(MemberRole.id).where(
        MemberRole.user_id == Member.id, MemberRole.role.in_(DESIGN_ROLES)).exists()]
    if search:
        filters.append(or_(Member.name.icontains(search, autoescape=True),
                           Member.department.icontains(search, autoescape=True)))
    total = session.scalar(select(func.count()).select_from(Member).where(*filters))
    records = session.scalars(select(Member).where(*filters).order_by(Member.name, Member.id)
                             .offset((page - 1) * page_size).limit(page_size))
    return {'items': [{'id': str(item.id), 'name': item.name, 'department': item.department} for item in records],
            'total': total, 'page': page, 'pageSize': page_size}
