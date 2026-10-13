"""Explicit, once-only grant to identities already verified by the identity service."""
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.db import require_overseas_context, session_factory
from app.overseas.members.models import MemberAudit
from app.overseas.members.service import active_admin_ids, lock_permissions
from app.overseas.members import membership
from app.membership.service import event, snapshot
from app.db.timestamps import utcnow


def bootstrap_admins(session, corp_id: str, user_ids: str):
    corp_id = corp_id.strip()
    targets = sorted({value.strip() for value in user_ids.split(',') if value.strip()})
    if not corp_id or not targets:
        raise ValueError('必须明确配置海外初始化企业和成员标识')
    lock_permissions(session)
    members = list(session.scalars(select(Member).where(
        Member.corp_id == corp_id, Member.provider_user_id.in_(targets),
    ).execution_options(populate_existing=True)))
    prior = set(session.scalars(select(MemberAudit.member_id).where(MemberAudit.action == 'bootstrap')))
    selected = {member.id for member in members}
    admins = active_admin_ids(session)
    if prior:
        if len(members) == len(targets) and prior == selected and selected <= admins:
            return 0
        raise ValueError('海外管理员初始化已完成，禁止重新提权')
    if admins:
        raise ValueError('已有有效海外超级管理员，拒绝初始化')
    applications = list(session.scalars(select(membership.Application).where(
        membership.Application.corp_id == corp_id,
        membership.Application.provider_user_id.in_(targets),
        membership.Application.status == 'pending',
    ).execution_options(populate_existing=True)))
    if len(applications) != len(targets):
        raise ValueError('初始化成员必须先明确提交海外加入申请')
    for application in applications:
        before = snapshot(application)
        member = membership.enroll(session, application, 'super_admin', None, 'bootstrap')
        application.status, application.version = 'approved', application.version + 1
        application.updated_at = utcnow()
        event(session, membership, application, 'bootstrap', before,
              memberId=str(member.id), role='super_admin')
    session.commit()
    return len(applications)



def main():
    require_overseas_context()
    settings = get_settings()
    with session_factory()() as session:
        try:
            count = bootstrap_admins(session, settings.bootstrap_admin_corp_id,
                                     settings.bootstrap_admin_user_ids)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
    print(f'海外管理员初始化完成：{count} 名成员变更')


if __name__ == '__main__':
    main()
