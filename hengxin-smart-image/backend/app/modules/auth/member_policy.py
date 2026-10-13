"""Domestic permission writers share one lock and recheck current authorization."""
from fastapi import HTTPException
from sqlalchemy import select, text

from app.resource_models import UserRecord

ROLES = ('super_admin', 'design_manager', 'designer', 'operator')
PERMISSION_LOCK = 7318041801


def lock_permissions(session):
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': PERMISSION_LOCK})


def require_admin(session, actor_id):
    actor = session.scalar(select(UserRecord).where(UserRecord.id == actor_id)
                           .execution_options(populate_existing=True))
    if (actor is None or actor.directory_state != 'enrolled'
            or actor.status != 'active' or actor.role != 'super_admin'):
        raise HTTPException(403, '没有国内成员管理权限')
    return actor


def snapshot(member):
    return {'role': member.role, 'status': member.status, 'directoryState': member.directory_state}


def audit_member(session, member, actor_id, action, before):
    from app.modules.auth.application_models import MemberAudit
    session.add(MemberAudit(member_id=member.id, actor_id=actor_id, action=action,
                            before=before, after=snapshot(member)))
