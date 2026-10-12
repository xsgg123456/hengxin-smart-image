"""Overseas policy; one scope definition for SQL lists and individual actions."""
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import false, or_, true
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.overseas.auth.dependencies import get_current_member, member_roles
from app.overseas.auth.models import Member, ROLES

CAPABILITIES = ('task.read', 'task.create', 'task.design', 'task.reassign',
                'stats.read', 'members.manage', 'skills.manage', 'settings.manage')
MANAGERS = frozenset(('operator_manager', 'design_manager', 'super_admin'))


@dataclass(frozen=True)
class Principal:
    id: UUID
    roles: frozenset[str]


def scopes(roles, permission):
    """Unknown roles/permissions never grant access, even alongside a valid role."""
    roles = frozenset(roles)
    if not roles or not roles <= set(ROLES) or permission not in CAPABILITIES:
        return frozenset()
    if permission in ('task.read', 'stats.read'):
        if roles & MANAGERS:
            return frozenset(('all',))
        return frozenset(scope for role, scope in (('operator', 'created'), ('designer', 'assigned'))
                         if role in roles)
    if permission == 'task.design':
        return frozenset(('all',)) if 'design_manager' in roles else (
            frozenset(('assigned',)) if 'designer' in roles else frozenset())
    allowed = {
        'task.create': {'operator', 'operator_manager'},
        'task.reassign': {'design_manager', 'super_admin'},
        'members.manage': {'super_admin'},
        'skills.manage': {'super_admin'},
        'settings.manage': {'super_admin'},
    }
    return frozenset(('all',)) if roles & allowed.get(permission, set()) else frozenset()


def capabilities(roles) -> list[str]:
    return [permission for permission in CAPABILITIES if scopes(roles, permission)]


def principal_for(session: Session, member: Member) -> Principal:
    return Principal(member.id, frozenset(member_roles(session, member)))


def authorize_member(session: Session, member: Member, permission: str):
    if not scopes(principal_for(session, member).roles, permission):
        raise HTTPException(403, '没有海外业务操作权限')
    return member


def require_permission(permission: str):
    def dependency(member=Depends(get_current_member), session: Session = Depends(get_session)):
        return authorize_member(session, member, permission)
    return dependency


def task_filter(principal: Principal, created_by, designer_id, permission='task.read'):
    """Apply to task queries before pagination/counting; caller supplies overseas columns."""
    scope = scopes(principal.roles, permission)
    if 'all' in scope:
        return true()
    conditions = []
    if 'created' in scope:
        conditions.append(created_by == principal.id)
    if 'assigned' in scope:
        conditions.append(designer_id == principal.id)
    return or_(*conditions) if conditions else false()


def can_access_task(principal: Principal, created_by, designer_id, permission='task.read') -> bool:
    scope = scopes(principal.roles, permission)
    return ('all' in scope or ('created' in scope and created_by == principal.id)
            or ('assigned' in scope and designer_id == principal.id))


def require_task_access(principal: Principal, created_by, designer_id, permission='task.read'):
    if not can_access_task(principal, created_by, designer_id, permission):
        raise HTTPException(403, '没有该海外任务的操作权限')
