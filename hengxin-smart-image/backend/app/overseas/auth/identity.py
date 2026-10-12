"""Map an identity assertion into this business without granting any roles."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.overseas.auth.models import Member


def bind_member(session, identity: dict):
    query = select(Member).where(
        Member.corp_id == identity['corp_id'],
        Member.provider_user_id == identity['provider_user_id'],
    )
    member = session.scalar(query)
    if member is None:
        try:
            with session.begin_nested():
                member = Member(**identity, status='pending')
                session.add(member)
                session.flush()
        except IntegrityError:
            member = session.scalar(query)
            if member is None:
                raise
    member.name = identity['name']
    member.union_id = identity.get('union_id')
    member.department = identity.get('department') or ''
    return member
