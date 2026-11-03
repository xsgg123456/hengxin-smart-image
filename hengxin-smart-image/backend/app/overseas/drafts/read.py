"""Read a draft in one snapshot; only first creation uses the write locks."""
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.overseas.auth.models import Member
from app.overseas.permissions import authorize_member
from . import service
from .models import RequirementDraft


def snapshot(bind, owner_id):
    with Session(bind=bind, autoflush=False) as reader:
        if bind.dialect.name == 'postgresql':
            # Must precede the first SQL/autobegin on this fresh session.
            reader.connection(execution_options={
                'isolation_level': 'REPEATABLE READ', 'postgresql_readonly': True,
            })
        member = reader.get(Member, owner_id)
        if member is None:
            raise HTTPException(403, '海外账号无效')
        authorize_member(reader, member, 'task.create')
        draft = reader.scalar(select(RequirementDraft).where(RequirementDraft.owner_id == owner_id))
        return service.describe(reader, draft) if draft is not None else None
    # Session.close rolls back the snapshot and returns its connection on every exit.


def get(session, actor):
    owner_id, bind = actor.id, session.get_bind()
    # Authentication already began a transaction. Release it before acquiring the
    # snapshot connection; never change isolation on an active transaction.
    session.rollback()
    result = snapshot(bind, owner_id)
    if result is not None:
        return result
    with Session(bind=bind) as writer, writer.begin():
        service.owned(writer, SimpleNamespace(id=owner_id))
    # Creation's locks are released before the multi-query response is read.
    result = snapshot(bind, owner_id)
    if result is None:
        raise HTTPException(409, '草稿已变更，请重新加载')
    return result
