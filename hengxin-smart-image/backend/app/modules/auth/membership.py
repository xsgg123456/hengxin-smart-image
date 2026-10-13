"""Domestic model adapter. No overseas metadata is imported."""
from fastapi import HTTPException
from sqlalchemy import select

from app.contracts.business import User
from app.modules.auth.application_models import MembershipApplication as Application, ApplicationEvent as Event
from app.modules.auth.member_policy import ROLES as roles, lock_permissions as lock, require_admin
from app.modules.auth.member_policy import audit_member, snapshot
from app.modules.auth.models import RoleAssignmentRecord, UserIdentityRecord
from app.resource_models import UserRecord


def find_member(session, identity):
    return session.scalar(select(UserRecord).join(UserIdentityRecord,
        UserIdentityRecord.user_id == UserRecord.id).where(
        UserIdentityRecord.provider == 'dingtalk',
        UserIdentityRecord.corp_id == identity['corp_id'],
        UserIdentityRecord.provider_user_id == identity['provider_user_id'],
    ).execution_options(populate_existing=True))


def is_allowed(session, member):
    return member.status == 'active' and member.role in roles


def describe_member(session, member, identity_session_id):
    return User(id=str(member.id), name=member.name, role=member.role, status=member.status,
                identitySessionId=identity_session_id)


def enroll(session, application, role, actor_id):
    identity = {key: getattr(application, key) for key in
                ('corp_id', 'provider_user_id', 'union_id', 'name', 'department')}
    member = find_member(session, identity)
    before = snapshot(member) if member else {}
    if member is not None:
        if member.status == 'disabled' or member.directory_state == 'enrolled':
            raise HTTPException(409, '成员归属已变更，请通过成员管理维护权限')
        member.name, member.role, member.status = application.name, role, 'active'
        member.directory_state = 'enrolled'
    else:
        member = UserRecord(name=application.name, role=role, status='active',
                            identity_source='dingtalk', directory_state='enrolled')
        session.add(member)
        session.flush()
        session.add(UserIdentityRecord(user_id=member.id, provider='dingtalk',
            corp_id=application.corp_id, provider_user_id=application.provider_user_id,
            union_id=application.union_id, department=application.department))
    assignment = session.scalar(select(RoleAssignmentRecord).where(
        RoleAssignmentRecord.user_id == member.id))
    if assignment is None:
        session.add(RoleAssignmentRecord(user_id=member.id, role=role, assigned_by=actor_id))
    else:
        assignment.role, assignment.assigned_by = role, actor_id
    session.flush()
    audit_member(session, member, actor_id, 'application_approve', before)
    return member
