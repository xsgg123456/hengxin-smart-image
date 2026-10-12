from datetime import timedelta

from fastapi import HTTPException
import pytest
from sqlalchemy import select

from app.core import browser_auth
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.main import app
from app.modules.auth.dependencies import get_identity_id
from app.modules.auth.models import AuthSessionRecord, UserIdentityRecord
from app.modules.auth.sessions import SESSION_COOKIE, issue_session
from app.resource_models import UserRecord
from files_helpers import files_env


@pytest.fixture
def bridge(files_env, monkeypatch):
    client, factory, _, identity = files_env
    settings = get_settings()
    monkeypatch.setattr(settings, 'identity_service_url', 'http://identity.test')
    monkeypatch.setattr(settings, 'identity_service_key', 'test-service-key-' * 3)
    member = {'corp_id': 'corp-1', 'provider_user_id': 'authorized', 'union_id': 'union-1',
              'name': '已授权国内成员', 'department': ''}
    assertion = {'member': member, 'identity_session_id': 'identity-session-1',
                 'expires_at': (utcnow() + timedelta(minutes=10)).isoformat()}
    monkeypatch.setattr(browser_auth, 'redeem_ticket', lambda *args: assertion)
    monkeypatch.setattr(browser_auth, 'check_identity', lambda *args: True)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).identity_source = 'dingtalk'
        session.add(UserIdentityRecord(user_id=identity[0], provider='dingtalk', **{
            key: member[key] for key in ('corp_id', 'provider_user_id', 'union_id', 'department')
        }))
    app.dependency_overrides.pop(get_identity_id)
    return client, factory, assertion, identity[0]


def exchange(client):
    return client.post('/api/v1/auth/identity/session', json={'ticket': 'opaque-ticket'},
                       headers={'X-HX-Request': '1'})


def test_unified_session_keeps_domestic_cookie_and_authorization(bridge):
    client, factory, _, _ = bridge
    response = exchange(client)
    assert response.status_code == 200
    assert response.headers['set-cookie'].startswith('hx_session=')
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/v1/auth/me').status_code == 200
    with factory() as session:
        record = session.scalar(select(AuthSessionRecord))
        assert record.identity_session_id == 'identity-session-1'
        assert record.expires_at.replace(tzinfo=utcnow().tzinfo) <= utcnow() + timedelta(minutes=10)


def test_global_revocation_does_not_affect_legacy_sessions(bridge, monkeypatch):
    client, factory, _, user_id = bridge
    assert exchange(client).status_code == 200
    monkeypatch.setattr(browser_auth, 'check_identity', lambda *args: False)
    assert client.get('/api/v1/auth/me').status_code == 401
    with factory.begin() as session:
        legacy_token = issue_session(session, user_id)
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, legacy_token)
    assert client.get('/api/v1/auth/me').status_code == 200


def test_pending_and_disabled_do_not_get_domestic_business_access(bridge):
    client, factory, assertion, user_id = bridge
    with factory.begin() as session:
        session.get(UserRecord, user_id).status = 'disabled'
    assert exchange(client).status_code == 403
    assertion['member']['provider_user_id'] = 'new-unprivileged'
    assert exchange(client).status_code == 403
    with factory() as session:
        assert session.scalar(select(AuthSessionRecord)) is None
        assert session.scalar(select(UserRecord).where(UserRecord.status == 'pending')) is not None


def test_failed_exchange_and_untrusted_request_create_no_session(bridge, monkeypatch):
    client, factory, _, _ = bridge

    def rejected(*args):
        raise HTTPException(401, 'invalid ticket')

    monkeypatch.setattr(browser_auth, 'redeem_ticket', rejected)
    assert exchange(client).status_code == 401
    assert client.post('/api/v1/auth/identity/session', json={'ticket': 'opaque'}).status_code == 403
    with factory() as session:
        assert session.scalar(select(AuthSessionRecord)) is None


def test_switch_to_unprivileged_identity_revokes_previous_domestic_cookie(bridge):
    client, factory, assertion, user_id = bridge
    with factory.begin() as session:
        legacy_token = issue_session(session, user_id)
    client.cookies.set(SESSION_COOKIE, legacy_token)
    assertion['member']['provider_user_id'] = 'unprivileged-new-user'
    assert exchange(client).status_code == 403
    assert client.get('/api/v1/auth/me').status_code == 401
