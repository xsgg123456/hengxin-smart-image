from datetime import timedelta

import pytest
from sqlalchemy import MetaData, select

from app.core import browser_auth
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.membership import service
from app.modules.auth import membership as domestic
from app.modules.auth.models import AuthSessionRecord, UserIdentityRecord
from app.resource_models import UserRecord
from app.overseas.auth.models import BusinessSession, Member, MemberRole
from app.overseas.members import membership as overseas_adapter
from files_helpers import files_env
from test_overseas_auth import overseas, HEADERS

IDENTITY = {'corp_id': 'corp', 'provider_user_id': 'applicant', 'name': '同名员工',
            'union_id': 'union', 'department': '部门'}


@pytest.fixture(params=['domestic', 'overseas'])
def membership_env(request, monkeypatch):
    business = request.param
    if business == 'domestic':
        client, factory, _, actor_ids = request.getfixturevalue('files_env')
        with factory.begin() as session:
            session.get(UserRecord, actor_ids[0]).role = 'super_admin'
        assertion = {'member': IDENTITY.copy(), 'identity_session_id': 'applicant-session',
                     'expires_at': (utcnow() + timedelta(minutes=20)).isoformat()}
        settings = get_settings()
        monkeypatch.setattr(settings, 'identity_service_url', 'http://identity.test')
        monkeypatch.setattr(settings, 'identity_service_key', 'test-service-key-' * 3)
        monkeypatch.setattr(settings, 'identity_public_origin', 'http://testserver')
        monkeypatch.setattr(browser_auth, 'redeem_ticket', lambda *args: assertion)
        monkeypatch.setattr(browser_auth, 'check_identity', lambda *args: True)
        adapter, members, sessions = domestic, UserRecord, AuthSessionRecord
        base, management, actor_id = '/api/v1', '/management/users', actor_ids[0]
    else:
        client, factory, assertion = request.getfixturevalue('overseas')
        from test_overseas_auth import seed, login
        actor_id = seed(factory, roles=('super_admin',))
        assert login(client).status_code == 200
        assertion['member'] = IDENTITY.copy()
        assertion['identity_session_id'] = 'applicant-session'
        adapter, members, sessions = overseas_adapter, Member, BusinessSession
        base, management = '/api/overseas/v1', '/members'
    return {'client': client, 'factory': factory, 'assertion': assertion, 'adapter': adapter,
            'members': members, 'sessions': sessions, 'base': base,
            'management': base + management, 'actor_id': actor_id, 'business': business}


def post(env, operation, **extra):
    return env['client'].post(env['base'] + '/auth/identity/' + operation,
                              json={'ticket': 'purpose-bound-ticket', **extra}, headers=HEADERS)


def decide(env, application, decision='approve', role='designer', **extra):
    body = {'decision': decision, 'version': application['version'], **extra}
    if role is not None:
        body['role'] = role
    return env['client'].post(env['management'] + '/applications/' + application['id'] + '/decision',
                              json=body, headers=HEADERS)


def seed_applicant(env, status='active', directory='enrolled', role='designer'):
    with env['factory'].begin() as session:
        if env['business'] == 'domestic':
            member = UserRecord(name=IDENTITY['name'], role=role, status=status,
                                identity_source='dingtalk', directory_state=directory)
            session.add(member)
            session.flush()
            session.add(UserIdentityRecord(user_id=member.id, provider='dingtalk',
                corp_id=IDENTITY['corp_id'], provider_user_id=IDENTITY['provider_user_id'],
                union_id=IDENTITY['union_id'], department=IDENTITY['department']))
        else:
            member = Member(**IDENTITY, status=status, directory_state=directory)
            session.add(member)
            session.flush()
            if role:
                session.add(MemberRole(user_id=member.id, role=role))
        return member.id


def db_snapshot(env):
    with env['factory']() as session:
        metadata = MetaData()
        metadata.reflect(session.get_bind())
        return {table.name: [tuple(row) for row in session.execute(select(table))]
                for table in metadata.tables.values()}
