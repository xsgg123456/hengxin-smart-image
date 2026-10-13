"""Look up verified identity; only explicit application approval may create members."""
from fastapi import HTTPException
from sqlalchemy import select

from app.overseas.auth.models import Member


def find_member(session, identity: dict):
    return session.scalar(select(Member).where(
        Member.corp_id == identity['corp_id'],
        Member.provider_user_id == identity['provider_user_id'],
    ).execution_options(populate_existing=True))


def bind_member(session, identity: dict):
    member = find_member(session, identity)
    if member is None or member.directory_state != 'enrolled':
        raise HTTPException(403, '尚未加入海外业务，请在统一入口申请权限')
    return member
