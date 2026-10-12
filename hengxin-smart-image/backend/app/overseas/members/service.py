from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.db.timestamps import utcnow
from app.overseas.auth.models import BusinessSession, Member, MemberRole
from app.overseas.members.models import MemberAudit
from app.overseas.members.schemas import MemberPatch
from app.overseas.permissions import authorize_member

# One transaction lock for every permission writer, including explicit bootstrap.
PERMISSION_LOCK = 7318041802


def lock_permissions(session: Session):
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': PERMISSION_LOCK})


def get_member(session: Session, member_id: UUID):
    member = session.scalar(select(Member).where(Member.id == member_id)
                            .execution_options(populate_existing=True))
    if member is None:
        raise HTTPException(404, '海外成员不存在')
    return member


def roles_for(session: Session, member_id: UUID):
    return list(session.scalars(select(MemberRole.role).where(
        MemberRole.user_id == member_id).order_by(MemberRole.role)))


def snapshot(session, member):
    return {'roles': roles_for(session, member.id), 'status': member.status,
            'version': member.version}


def describe(session, member):
    return {'id': str(member.id), 'name': member.name, 'department': member.department,
            **snapshot(session, member), 'createdAt': member.created_at,
            'updatedAt': member.updated_at}


def list_members(session, search='', status=None, role=None, page=1, page_size=20):
    filters = []
    if search:
        filters.append(or_(Member.name.icontains(search, autoescape=True),
                           Member.department.icontains(search, autoescape=True)))
    if status:
        filters.append(Member.status == status)
    if role:
        filters.append(select(MemberRole.id).where(
            MemberRole.user_id == Member.id, MemberRole.role == role).exists())
    total = session.scalar(select(func.count()).select_from(Member).where(*filters))
    members = session.scalars(select(Member).where(*filters).order_by(
        Member.created_at.desc(), Member.id).offset((page - 1) * page_size).limit(page_size))
    return {'items': [describe(session, member) for member in members], 'total': total,
            'page': page, 'pageSize': page_size}


def active_admin_ids(session):
    return set(session.scalars(select(Member.id).join(MemberRole, MemberRole.user_id == Member.id)
                              .where(Member.status == 'active', MemberRole.role == 'super_admin')))


def write_change(session, member, roles, status, actor_id, action):
    before = snapshot(session, member)
    session.execute(delete(MemberRole).where(MemberRole.user_id == member.id))
    session.add_all([MemberRole(user_id=member.id, role=role) for role in roles])
    member.status = status
    member.version += 1
    member.updated_at = utcnow()
    if status == 'disabled':
        session.execute(update(BusinessSession).where(
            BusinessSession.user_id == member.id, BusinessSession.revoked_at.is_(None),
        ).values(revoked_at=utcnow()))
    session.add(MemberAudit(member_id=member.id, actor_id=actor_id, action=action,
                            before=before, after={'roles': sorted(roles), 'status': status,
                                                  'version': member.version}))
    session.flush()


def patch_member(session, actor, member_id, body: MemberPatch):
    lock_permissions(session)
    actor = get_member(session, actor.id)
    authorize_member(session, actor, 'members.manage')
    member = get_member(session, member_id)
    if member.version != body.version:
        raise HTTPException(409, '成员已被修改，请刷新后重试')
    admins = active_admin_ids(session)
    if member.id in admins and (body.status != 'active' or 'super_admin' not in body.roles):
        if len(admins) <= 1:
            raise HTTPException(409, '不能停用或移除最后一名有效超级管理员')
    write_change(session, member, body.roles, body.status, actor.id, 'update')
    result = describe(session, member)
    session.commit()
    return result


def audit_entries(session, member_id):
    get_member(session, member_id)
    entries = session.scalars(select(MemberAudit).where(MemberAudit.member_id == member_id)
                              .order_by(MemberAudit.created_at.desc(), MemberAudit.id).limit(100))
    return {'items': [{'id': str(entry.id), 'actorId': str(entry.actor_id) if entry.actor_id else None,
                       'action': entry.action, 'before': entry.before, 'after': entry.after,
                       'createdAt': entry.created_at} for entry in entries]}
