from datetime import datetime, timedelta
import runpy
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import browser_auth
from app.core.config import get_settings
from app.db.session import get_session
from app.db.timestamps import utcnow
from app.overseas.auth.models import BusinessSession, Member, MemberRole
from app.overseas.auth.sessions import COOKIE_PATH, SESSION_COOKIE
from app.overseas.db import Base
from test_overseas_configuration import FAKE_OVERSEAS

HEADERS = {'X-HX-Request': '1'}
MEMBER = {'corp_id': 'corp', 'provider_user_id': 'member-1', 'union_id': 'union-1',
          'name': '海外成员', 'department': '设计部'}


@pytest.fixture
def overseas(monkeypatch):
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', 'overseas')
    for key, value in FAKE_OVERSEAS.items():
        monkeypatch.setenv('OVERSEAS_' + key, value)
    get_settings.cache_clear()
    settings = get_settings()
    settings.identity_service_url = 'http://identity.test'
    settings.identity_service_key = 'test-service-key-' * 3
    settings.identity_public_origin = 'http://testserver'
    assertion = {'member': MEMBER, 'identity_session_id': 'identity-1',
                 'expires_at': (utcnow() + timedelta(minutes=20)).isoformat()}
    monkeypatch.setattr(browser_auth, 'redeem_ticket', lambda *args: assertion)
    monkeypatch.setattr(browser_auth, 'check_identity', lambda *args: True)
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    app = runpy.run_path(str(Path(__file__).parents[1] / 'app/overseas/main.py'))['app']

    def session_dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    try:
        with TestClient(app) as client:
            yield client, factory, assertion
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        get_settings.cache_clear()


def seed(factory, status='active', roles=('designer',)):
    with factory.begin() as session:
        member = Member(id=uuid4(), **MEMBER, status=status)
        session.add(member)
        session.flush()
        for role in roles:
            session.add(MemberRole(user_id=member.id, role=role))
        return member.id


def login(client, **extra):
    return client.post(COOKIE_PATH + '/auth/identity/session',
                       json={'ticket': 'single-use-ticket', **extra}, headers=HEADERS)


def test_authorized_member_gets_only_overseas_cookie_and_real_roles(overseas):
    client, factory, assertion = overseas
    seed(factory, roles=('designer', 'operator'))
    response = login(client)
    assert response.status_code == 200
    assert response.json()['roles'] == ['designer', 'operator']
    cookie = response.headers['set-cookie']
    assert cookie.startswith(SESSION_COOKIE + '=') and 'HttpOnly' in cookie
    assert 'Path=' + COOKIE_PATH in cookie and 'SameSite=lax' in cookie
    assert 'hx_session=' not in cookie
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 200
    with factory() as session:
        record = session.scalar(select(BusinessSession))
        assert record.identity_session_id == 'identity-1'
        assert record.token_hash != client.cookies.get(SESSION_COOKIE)
        assert len(record.token_hash) == 64
        assert record.expires_at.replace(tzinfo=utcnow().tzinfo) <= datetime.fromisoformat(assertion['expires_at'])


@pytest.mark.parametrize('status,roles', [('pending', ('designer',)), ('disabled', ('designer',)), ('active', ())])
def test_pending_disabled_and_roleless_member_cannot_create_session(overseas, status, roles):
    client, factory, _ = overseas
    seed(factory, status=status, roles=roles)
    assert login(client).status_code == 403
    with factory() as session:
        assert session.scalar(select(BusinessSession)) is None


def test_unknown_member_registered_pending_without_domestic_admin_promotion(overseas, monkeypatch):
    client, factory, _ = overseas
    monkeypatch.setenv('DINGTALK_ADMIN_USER_IDS', 'member-1')
    assert login(client).status_code == 403
    with factory() as session:
        assert session.scalar(select(Member)).status == 'pending'
        assert session.scalar(select(MemberRole)) is None
        assert session.scalar(select(BusinessSession)) is None


def test_domestic_cookie_and_forged_roles_cannot_authenticate(overseas):
    client, factory, _ = overseas
    seed(factory)
    client.cookies.set('hx_session', 'domestic-token')
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 401
    assert login(client, roles=['super_admin']).status_code == 422
    assert client.post(COOKIE_PATH + '/auth/identity/session', json={'ticket': 't'}).status_code == 403


def test_revoked_identity_and_dependency_outage_fail_closed(overseas, monkeypatch):
    client, factory, _ = overseas
    seed(factory)
    assert login(client).status_code == 200
    monkeypatch.setattr(browser_auth, 'check_identity', lambda *args: False)
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 401

    def unavailable(*args):
        raise HTTPException(503, '身份服务暂不可用')

    monkeypatch.setattr(browser_auth, 'check_identity', unavailable)
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 503


def test_local_disable_and_expiry_are_checked_on_every_request(overseas):
    client, factory, _ = overseas
    identifier = seed(factory)
    assert login(client).status_code == 200
    with factory.begin() as session:
        session.get(Member, identifier).status = 'disabled'
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 403
    with factory.begin() as session:
        session.get(Member, identifier).status = 'active'
        session.scalar(select(BusinessSession)).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 401


def test_local_logout_revokes_session_and_requires_request_header(overseas):
    client, factory, _ = overseas
    seed(factory)
    assert login(client).status_code == 200
    token = client.cookies.get(SESSION_COOKIE)
    assert client.post(COOKIE_PATH + '/auth/logout').status_code == 403
    response = client.post(COOKIE_PATH + '/auth/logout', headers=HEADERS)
    assert response.status_code == 204
    assert 'Path=' + COOKIE_PATH in response.headers['set-cookie']
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 401


def test_switch_identity_cannot_retain_another_members_business_session(overseas):
    client, factory, assertion = overseas
    seed(factory)
    assert login(client).status_code == 200
    assertion['member'] = {**MEMBER, 'provider_user_id': 'pending-new-member'}
    assert login(client).status_code == 403
    assert client.get(COOKIE_PATH + '/auth/me').status_code == 401
