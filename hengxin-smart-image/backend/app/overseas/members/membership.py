"""Overseas adapter; grants and audits share the existing permission transaction."""
from fastapi import HTTPException

from app.overseas.auth.identity import find_member
from app.overseas.auth.models import Member, ROLES as roles
from app.overseas.auth.router import describe as describe_member
from app.overseas.members.application_models import MembershipApplication as Application, ApplicationEvent as Event
from app.overseas.members.service import get_member, lock_permissions as lock, roles_for, write_change
from app.overseas.permissions import authorize_member


def is_allowed(session, member):
    assigned = roles_for(session, member.id)
    return member.status == 'active' and len(assigned) == 1 and assigned[0] in roles


def require_admin(session, actor_id):
    return authorize_member(session, get_member(session, actor_id), 'members.manage')


def enroll(session, application, role, actor_id, action='application_approve'):
    identity = {key: getattr(application, key) for key in
                ('corp_id', 'provider_user_id', 'union_id', 'name', 'department')}
    member = find_member(session, identity)
    if member is not None:
        if member.status == 'disabled' or member.directory_state == 'enrolled':
            raise HTTPException(409, '成员归属已变更，请通过成员管理维护权限')
        member.name = application.name
    else:
        member = Member(**identity, status='pending', directory_state='legacy_unconfirmed')
        session.add(member)
        session.flush()
    member.directory_state = 'enrolled'
    write_change(session, member, [role], 'active', actor_id, action)
    return member
