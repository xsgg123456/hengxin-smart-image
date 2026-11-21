"""Overseas policy; one scope definition for SQL lists and individual actions."""
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.core.config import get_settings
from app.overseas.auth.dependencies import get_current_member, member_roles
from app.overseas.auth.models import Member, ROLES
from app.overseas.feedback.models import FeedbackGrant
from app.overseas.tasks.creative_tools import TOOL_KEYS

CAPABILITIES = ('task.read', 'task.create', 'task.tool.create', 'task.design', 'task.reassign', 'task.delete',
                'stats.read', 'members.manage', 'skills.manage', 'settings.manage')
MANAGERS = frozenset(('design_manager', 'super_admin'))


@dataclass(frozen=True)
class Principal:
    id: UUID
    roles: frozenset[str]
    workflow_collaborator: bool = False


def scopes(roles, permission):
    """Unknown roles/permissions never grant access, even alongside a valid role."""
    roles = frozenset(roles)
    if len(roles) != 1 or not roles <= set(ROLES) or permission not in CAPABILITIES:
        return frozenset()
    if 'super_admin' in roles:
        return frozenset(('all',))
    if permission == 'task.tool.create':
        return frozenset(('all',))
    if roles == {'non_designer'} and permission in ('task.read', 'task.design'):
        return frozenset(('own_tool',))
    if permission in ('task.read', 'stats.read'):
        if roles & MANAGERS:
            return frozenset(('all',))
        return frozenset(('created', 'assigned')) if 'designer' in roles else frozenset()
    if permission == 'task.design':
        return frozenset(('all',)) if 'design_manager' in roles else (
            frozenset(('assigned',)) if 'designer' in roles else frozenset())
    allowed = {
        'task.create': {'designer', 'design_manager'},
        'task.reassign': {'design_manager', 'super_admin'},
        'members.manage': {'super_admin'},
        'skills.manage': {'super_admin'},
        'settings.manage': {'super_admin'},
    }
    return frozenset(('all',)) if roles & allowed.get(permission, set()) else frozenset()


def capabilities(roles) -> list[str]:
    return [permission for permission in CAPABILITIES if scopes(roles, permission)]


def has_full_access_grant(member: Member | None) -> bool:
    return (member is not None and member.status == 'active'
            and member.directory_state == 'enrolled'
            and member.id in getattr(get_settings(), 'full_access_member_ids', frozenset()))


def principal_for(session: Session, member: Member) -> Principal:
    # Validate membership and the real single role before applying an account grant.
    roles = member_roles(session, member)
    policy_roles = ('super_admin',) if roles != ['non_designer'] and has_full_access_grant(member) else roles
    collaborator = (roles == ['designer'] and member.id in getattr(
        get_settings(), 'workflow_collaborator_member_ids', frozenset()))
    return Principal(member.id, frozenset(policy_roles), collaborator)


def task_scopes(principal: Principal, permission: str):
    """Account grants expand workflow scope only, never role or statistics scope."""
    scope = scopes(principal.roles, permission)
    if principal.workflow_collaborator and principal.roles == {'designer'}:
        if permission == 'task.read':
            return frozenset(('all',))
        if permission == 'task.design':
            return frozenset(('created', 'assigned'))
    return scope


def can_submit_requirements(principal: Principal, created_by, designer_id) -> bool:
    if not scopes(principal.roles, 'task.create'):
        return False
    return (created_by == principal.id or bool(principal.roles & MANAGERS)
            or (principal.workflow_collaborator and principal.roles == {'designer'}
                and can_access_task(principal, created_by, designer_id, 'task.design')))


def can_manage_feedback(session: Session, member: Member, roles=None) -> bool:
    actual_roles = roles if roles is not None else member_roles(session, member)
    return bool(MANAGERS.intersection(actual_roles) and session.scalar(
        select(FeedbackGrant.id).where(FeedbackGrant.id == member.id)))


def authorize_member(session: Session, member: Member, permission: str):
    allowed = (can_manage_feedback(session, member) if permission == 'feedback.manage'
               else scopes(principal_for(session, member).roles, permission))
    if not allowed:
        raise HTTPException(403, '没有海外业务操作权限')
    return member


def require_permission(permission: str):
    def dependency(member=Depends(get_current_member), session: Session = Depends(get_session)):
        return authorize_member(session, member, permission)
    return dependency


def task_filter(principal: Principal, created_by, designer_id, permission='task.read', *, tool_key=None):
    """Apply to task queries before pagination/counting; caller supplies overseas columns."""
    scope = task_scopes(principal, permission)
    if 'all' in scope:
        return true()
    conditions = []
    if 'own_tool' in scope and tool_key is not None:
        conditions.append((created_by == principal.id) & tool_key.in_(TOOL_KEYS))
    if 'created' in scope:
        conditions.append(created_by == principal.id)
    if 'assigned' in scope:
        conditions.append(designer_id == principal.id)
    return or_(*conditions) if conditions else false()


def can_access_task(principal: Principal, created_by, designer_id, permission='task.read', *, tool_key=None) -> bool:
    scope = task_scopes(principal, permission)
    return ('all' in scope or ('created' in scope and created_by == principal.id)
            or ('assigned' in scope and designer_id == principal.id)
            or ('own_tool' in scope and created_by == principal.id and tool_key in TOOL_KEYS))


def require_task_access(principal: Principal, created_by, designer_id, permission='task.read', *, tool_key=None):
    if not can_access_task(principal, created_by, designer_id, permission, tool_key=tool_key):
        raise HTTPException(403, '没有该海外任务的操作权限')
