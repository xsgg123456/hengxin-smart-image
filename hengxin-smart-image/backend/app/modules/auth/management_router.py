from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.contracts import business as b, management as m
from app.db.session import get_session
from app.db.timestamps import utcnow
from app.modules.auth.member_policy import audit_member, lock_permissions, require_admin, snapshot
from app.modules.auth.models import AuthSessionRecord, RoleAssignmentRecord, UserIdentityRecord
from app.modules.auth.permissions import require_permission
from app.resource_models import UserRecord

router = APIRouter(tags=['management'])


def _department_expression():
    return select(UserIdentityRecord.department).where(
        UserIdentityRecord.user_id == UserRecord.id,
    ).order_by(UserIdentityRecord.created_at.desc()).limit(1).scalar_subquery()


def _last_login_expression():
    return select(func.max(AuthSessionRecord.created_at)).where(
        AuthSessionRecord.user_id == UserRecord.id,
    ).scalar_subquery()


def _user_filters(query: m.UserQuery):
    state = 'enrolled' if query.directory == 'members' else 'legacy_unconfirmed'
    filters = [UserRecord.directory_state == state]
    if query.status:
        filters.append(UserRecord.status == query.status)
    if query.role:
        filters.append(UserRecord.role == query.role)
    if query.search:
        pattern = f'%{query.search}%'
        department_match = select(UserIdentityRecord.id).where(
            UserIdentityRecord.user_id == UserRecord.id,
            UserIdentityRecord.department.ilike(pattern),
        ).exists()
        filters.append(or_(UserRecord.name.ilike(pattern), department_match))
    return filters


def _managed_user(user: UserRecord, department: str | None, last_login_at):
    return m.ManagedUser(
        id=str(user.id), name=user.name, role=user.role, status=user.status,
        department=department or '',
        lastLoginAt=last_login_at.isoformat() if last_login_at else None,
    )


@router.get('/management/users', response_model=b.PageResult[m.ManagedUser], tags=['management'])
def list_users(
    query: Annotated[m.UserQuery, Query()],
    _: Annotated[UserRecord, Depends(require_permission('manage_system'))],
    session: Session = Depends(get_session),
):
    filters = _user_filters(query)
    total = session.scalar(select(func.count()).select_from(UserRecord).where(*filters)) or 0
    rows = session.execute(
        select(UserRecord, _department_expression(), _last_login_expression())
        .where(*filters)
        .order_by(UserRecord.created_at.desc(), UserRecord.id)
        .offset((query.page - 1) * query.pageSize)
        .limit(query.pageSize),
    ).all()
    return b.PageResult[m.ManagedUser](
        items=[_managed_user(user, department, last_login_at) for user, department, last_login_at in rows],
        page=query.page, pageSize=query.pageSize, total=total,
    )


@router.put('/management/users/{user_id}', response_model=m.ManagedUser, tags=['management'])
def update_user(
    user_id: str,
    body: m.UserInput,
    actor: Annotated[UserRecord, Depends(require_permission('manage_system'))],
    session: Session = Depends(get_session),
):
    try:
        target_id = UUID(user_id)
    except ValueError as error:
        raise HTTPException(422, '成员 ID 无效') from error
    if body.id != user_id:
        raise HTTPException(422, '请求成员 ID 与路径不一致')
    lock_permissions(session)
    require_admin(session, actor.id)
    target = session.get(UserRecord, target_id, populate_existing=True)
    if target is None:
        raise HTTPException(404, '成员不存在')
    if target.directory_state != 'enrolled':
        raise HTTPException(409, '历史成员尚未核对，请通过明确申请及审批确认归属')
    if body.status == 'active' and body.role is None:
        raise HTTPException(422, '启用账号前必须分配业务角色')
    removing_last_admin = (
        target.status == 'active' and target.role == 'super_admin'
        and (body.status != 'active' or body.role != 'super_admin')
    )
    if removing_last_admin:
        active_admins = session.scalar(select(func.count()).select_from(UserRecord).where(
            UserRecord.directory_state == 'enrolled',
            UserRecord.status == 'active', UserRecord.role == 'super_admin',
        )) or 0
        if active_admins <= 1:
            raise HTTPException(409, '系统至少需要一名启用中的超级管理员')
    before = snapshot(target)
    target.role, target.status = body.role, body.status
    if body.status != 'active' or body.role is None:
        session.execute(update(AuthSessionRecord).where(
            AuthSessionRecord.user_id == target.id, AuthSessionRecord.revoked_at.is_(None),
        ).values(revoked_at=utcnow()))
    assignment = session.scalar(select(RoleAssignmentRecord).where(
        RoleAssignmentRecord.user_id == target.id,
    ))
    if body.role is None:
        if assignment is not None:
            session.delete(assignment)
    elif assignment is None:
        session.add(RoleAssignmentRecord(user_id=target.id, role=body.role, assigned_by=actor.id))
    else:
        assignment.role, assignment.assigned_by = body.role, actor.id
    audit_member(session, target, actor.id, 'update', before)
    session.commit()
    department = session.scalar(select(UserIdentityRecord.department).where(
        UserIdentityRecord.user_id == target.id,
    ).order_by(UserIdentityRecord.created_at.desc()).limit(1))
    last_login_at = session.scalar(select(func.max(AuthSessionRecord.created_at)).where(
        AuthSessionRecord.user_id == target.id,
    ))
    return _managed_user(target, department, last_login_at)
