"""Explicit, once-only grant to identities already verified by the identity service."""
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.db import require_overseas_context, session_factory
from app.overseas.members.models import MemberAudit
from app.overseas.members.service import active_admin_ids, lock_permissions, roles_for, write_change


def bootstrap_admins(session, corp_id: str, user_ids: str):
    corp_id = corp_id.strip()
    targets = sorted({value.strip() for value in user_ids.split(',') if value.strip()})
    if not corp_id or not targets:
        raise ValueError('必须明确配置海外初始化企业和成员标识')
    lock_permissions(session)
    members = list(session.scalars(select(Member).where(
        Member.corp_id == corp_id, Member.provider_user_id.in_(targets),
    ).execution_options(populate_existing=True)))
    if len(members) != len(targets):
        raise ValueError('初始化成员尚未通过统一身份登记')
    prior = set(session.scalars(select(MemberAudit.member_id).where(MemberAudit.action == 'bootstrap')))
    selected = {member.id for member in members}
    admins = active_admin_ids(session)
    if prior:
        if prior == selected and selected <= admins:
            return 0
        raise ValueError('海外管理员初始化已完成，禁止重新提权')
    if admins:
        raise ValueError('已有有效海外超级管理员，拒绝初始化')
    for member in members:
        write_change(session, member, sorted(set(roles_for(session, member.id)) | {'super_admin'}),
                     'active', None, 'bootstrap')
    session.commit()
    return len(members)


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
