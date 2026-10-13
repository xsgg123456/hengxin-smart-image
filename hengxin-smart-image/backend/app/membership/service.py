"""Explicit applications shared by two isolated business adapters."""
from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import func, select

from app.db.timestamps import utcnow


def application_for(session, adapter, identity):
    model = adapter.Application
    return session.scalar(select(model).where(
        model.corp_id == identity['corp_id'],
        model.provider_user_id == identity['provider_user_id'],
    ).execution_options(populate_existing=True))


def describe(record):
    def timestamp(value):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    return {'id': str(record.id), 'name': record.name, 'status': record.status,
            'version': record.version, 'createdAt': timestamp(record.created_at),
            'updatedAt': timestamp(record.updated_at), 'reason': record.reason}


def snapshot(record):
    return {'status': record.status, 'version': record.version, 'reason': record.reason}


def event(session, adapter, record, action, before, actor_id=None, **extra):
    session.add(adapter.Event(application_id=record.id, actor_id=actor_id, action=action,
                              before=before, after={**snapshot(record), **extra}))


def state_for(session, adapter, member):
    if member is None:
        return 'unregistered'
    if member.status == 'disabled':
        return 'disabled'
    if member.directory_state != 'enrolled':
        return 'legacy_unconfirmed'
    return 'allowed' if adapter.is_allowed(session, member) else 'disabled'


def access(session, adapter, assertion):
    """Never update profiles, flush, commit, revoke or issue business sessions."""
    with session.no_autoflush:
        member = adapter.find_member(session, assertion['member'])
        state = state_for(session, adapter, member)
        if state == 'allowed':
            return {'state': state, 'member': adapter.describe_member(
                session, member, assertion['identity_session_id'])}
        if state == 'disabled':
            return {'state': state}
        application = application_for(session, adapter, assertion['member'])
        if application and application.status in ('pending', 'rejected'):
            return {'state': application.status, 'application': describe(application)}
        return {'state': state}


def submit(session, adapter, identity):
    adapter.lock(session)
    state = state_for(session, adapter, adapter.find_member(session, identity))
    if state == 'disabled':
        raise HTTPException(403, '账号已停用或撤权，请联系本业务管理员')
    if state == 'allowed':
        raise HTTPException(409, '已经加入本业务，无需申请')
    record = application_for(session, adapter, identity)
    if record and record.status == 'pending':
        return describe(record)
    before = snapshot(record) if record else {}
    if record is None:
        record = adapter.Application(**identity, status='pending', version=1)
        session.add(record)
    else:
        if record.status == 'approved':
            raise HTTPException(403, '已批准成员请联系本业务管理员恢复权限')
        record.name, record.union_id = identity['name'], identity.get('union_id')
        record.department = identity.get('department') or ''
        record.status, record.reason = 'pending', None
        record.version += 1
        record.updated_at = utcnow()
    session.flush()
    event(session, adapter, record, 'submit', before)
    session.commit()
    return describe(record)


def withdraw(session, adapter, identity):
    adapter.lock(session)
    record = application_for(session, adapter, identity)
    if record is None:
        raise HTTPException(404, '没有本业务加入申请')
    if record.status == 'withdrawn':
        return describe(record)
    if record.status != 'pending':
        raise HTTPException(409, '申请已经处理，不能撤回')
    before = snapshot(record)
    record.status, record.version = 'withdrawn', record.version + 1
    record.updated_at = utcnow()
    event(session, adapter, record, 'withdraw', before)
    session.commit()
    return describe(record)


def list_applications(session, adapter, status=None, page=1, page_size=20, search=''):
    model = adapter.Application
    filters = [model.status == status] if status else []
    if search:
        filters.append(model.name.icontains(search, autoescape=True))
    total = session.scalar(select(func.count()).select_from(model).where(*filters))
    rows = session.scalars(select(model).where(*filters).order_by(
        model.updated_at.desc(), model.id).offset((page - 1) * page_size).limit(page_size))
    return {'items': [describe(row) for row in rows], 'total': total,
            'page': page, 'pageSize': page_size}


def decide(session, adapter, actor, application_id, body):
    adapter.lock(session)
    adapter.require_admin(session, actor.id)
    record = session.scalar(select(adapter.Application).where(
        adapter.Application.id == application_id).execution_options(populate_existing=True))
    if record is None:
        raise HTTPException(404, '申请不存在')
    if body.role is not None and body.role not in adapter.roles:
        raise HTTPException(422, '请选择本业务合法角色')
    if record.version != body.version or record.status != 'pending':
        raise HTTPException(409, '申请已被处理，请刷新后重试')
    before = snapshot(record)
    member_id = None
    if body.decision == 'approve':
        member = adapter.enroll(session, record, body.role, actor.id)
        member_id = str(member.id)
    record.status = 'approved' if body.decision == 'approve' else 'rejected'
    record.reason, record.version = body.reason, record.version + 1
    record.updated_at = utcnow()
    event(session, adapter, record, body.decision, before, actor.id,
          memberId=member_id, role=body.role)
    session.commit()
    return describe(record)
