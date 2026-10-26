"""HTTP contract, real session permission checks, and broker allowlists."""
import pytest

from app.account_management import client as broker
from app.core.config import get_settings
from app.modules.auth.sessions import issue_session
from app.resource_models import UserRecord
from files_helpers import files_env
from test_overseas_auth import overseas, login, seed
from app.overseas.auth.models import Member, MemberRole
from sqlalchemy import select

ROOT = '/api/v1/management/codex-auth'
OVERSEAS = '/api/overseas/v1/management/codex-auth'
HEADERS = {'X-HX-Request': '1'}
ACCOUNT = dict(status='empty', email='', workspace='', checked='', updated='', audit=[],
               revision=0, checking=False)
AUTHORIZATION = dict(id='authorization-1', step='waiting', userCode='TEST-CODE',
                     verificationUrl='https://auth.openai.com/codex/device', expiresAt=1793000000,
                     candidateEmail='', candidateWorkspace='', different=False, message='')


@pytest.fixture
def management(files_env, monkeypatch):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
        token = issue_session(session, identity[0])
    client.cookies.set('hx_session', token)
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '/fake/domestic.sock')
    return client, factory, identity[0]


@pytest.fixture
def exchange(monkeypatch):
    calls = []

    def call(path, payload):
        calls.append((path, payload))
        if payload['action'] == 'cancel':
            return {'data': {'ok': True, 'refresh_token': 'secret'}}
        if payload['action'] in ('start', 'poll', 'retry'):
            return {'data': {**AUTHORIZATION, 'tokens': {'refresh_token': 'secret'}}}
        return {'data': {**ACCOUNT, 'auth_file': '/secret/auth.json', 'tokens': 'secret',
                         'audit': [dict(time='现在', operator='管理员', action='检测', result='成功',
                                        access_token='secret')]}}

    monkeypatch.setattr(broker, '_exchange', call)
    return calls


def test_routes_forward_server_actor_and_filter_sensitive_fields(management, exchange):
    client, _, actor = management
    cases = [('GET', '', None, 'status'), ('POST', '/check', None, 'check'),
             ('POST', '/authorizations', {'intent': 'renew', 'revision': 0}, 'start'),
             ('GET', '/authorizations/authorization-1', None, 'poll'),
             ('POST', '/authorizations/authorization-1/retry', None, 'retry'),
             ('POST', '/authorizations/authorization-1/activate', {'acknowledged': True}, 'activate'),
             ('DELETE', '/authorizations/authorization-1', None, 'cancel'),
             ('DELETE', '', {'revision': 0}, 'remove')]
    for method, suffix, body, action in cases:
        response = client.request(method, ROOT + suffix, json=body, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'private, no-store'
        assert 'secret' not in response.text and 'tokens' not in response.text
        path, payload = exchange[-1]
        assert path == '/fake/domestic.sock'
        assert payload['action'] == action
        assert payload['actor'] == {'id': str(actor), 'name': '测试操作者'}
        assert payload == {'action': action, 'actor': payload['actor'], **(body or {}),
                           **({'id': 'authorization-1'} if '/authorization-1' in suffix else {})}


@pytest.mark.parametrize('role', ['operator', 'designer', 'design_manager'])
def test_domestic_permissions_checked_on_every_request(management, exchange, role):
    client, factory, actor = management
    assert client.get(ROOT).status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, actor).role = role
    assert client.get(ROOT).status_code == 403
    assert client.post(ROOT + '/check', headers=HEADERS).status_code == 403
    assert len(exchange) == 1


def test_anonymous_and_other_business_cookie_fail_closed(management, exchange):
    client, _, _ = management
    client.cookies.clear()
    client.cookies.set('hx_overseas_session', 'forged')
    assert client.get(ROOT, headers={'X-Role': 'super_admin'}).status_code == 401
    assert client.get(OVERSEAS).status_code == 404
    assert not exchange


@pytest.mark.parametrize('method,suffix,body', [
    ('POST', '/check', None), ('POST', '/authorizations', {'intent': 'connect', 'revision': 0}),
    ('POST', '/authorizations/a/retry', None),
    ('POST', '/authorizations/a/activate', {'acknowledged': True}),
    ('DELETE', '/authorizations/a', None), ('DELETE', '', {'revision': 0}),
])
def test_all_mutations_require_csrf_and_same_origin(management, exchange, method, suffix, body):
    client, _, _ = management
    assert client.request(method, ROOT + suffix, json=body).status_code == 403
    response = client.request(method, ROOT + suffix, json=body,
                              headers={**HEADERS, 'Origin': 'https://evil.test'})
    assert response.status_code == 403
    assert not exchange


@pytest.mark.parametrize('method,suffix,body', [
    ('POST', '/check', {'actor': {'id': 'forged'}}),
    ('POST', '/authorizations', {'intent': 'connect', 'revision': 0, 'business': 'overseas'}),
    ('POST', '/authorizations', {'intent': 'connect', 'revision': True}),
    ('POST', '/authorizations', {'intent': 'connect', 'revision': -1}),
    ('POST', '/authorizations/a/retry', {'path': '/secret/auth.json'}),
    ('POST', '/authorizations/a/activate', {'acknowledged': True, 'actor': {}}),
    ('POST', '/authorizations/a/activate', {'acknowledged': 'true'}),
    ('DELETE', '/authorizations/a', {'business': 'overseas'}),
    ('DELETE', '', {'revision': 0, 'actor': {'id': 'forged'}}),
    ('GET', '?actor=forged', None), ('GET', '/authorizations/invalid.id', None),
])
def test_reject_client_identity_paths_context_and_invalid_fields(management, exchange, method, suffix, body):
    response = management[0].request(method, ROOT + suffix, json=body, headers=HEADERS)
    assert response.status_code == 422, response.text
    assert not exchange


@pytest.mark.parametrize('status', [400, 403, 404, 409, 503])
def test_broker_error_uses_existing_http_error_contract(management, monkeypatch, status):
    monkeypatch.setattr(broker, '_exchange', lambda *args: {
        'error': {'status': status, 'message': '授权流程已失效', 'access_token': 'secret'}})
    response = management[0].get(ROOT)
    assert response.status_code == status
    assert response.json()['message'] == '授权流程已失效'
    assert set(response.json()) == {'code', 'message', 'requestId'}


@pytest.mark.parametrize('response', [None, [], {}, {'data': {'refresh_token': 'secret'}},
    {'error': {'status': 500, 'message': 'secret'}}, {'data': ACCOUNT, 'secret': 'secret'}])
def test_malformed_broker_response_is_safe_503(management, monkeypatch, response):
    monkeypatch.setattr(broker, '_exchange', lambda *args: response)
    result = management[0].get(ROOT)
    assert result.status_code == 503
    assert 'secret' not in result.text


def test_absent_and_failed_socket_are_friendly(management, monkeypatch):
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '')
    response = management[0].get(ROOT)
    assert response.status_code == 503 and '尚未配置' in response.text
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '/secret/missing.sock')

    def failure(*args):
        raise OSError('/secret/missing.sock')

    monkeypatch.setattr(broker, '_exchange', failure)
    response = management[0].get(ROOT)
    assert response.status_code == 503 and '/secret' not in response.text


def test_overseas_permission_grant_revocation_and_socket_isolation(overseas, exchange, monkeypatch):
    client, factory, _ = overseas
    actor = seed(factory, roles=('designer',))
    assert login(client).status_code == 200
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '/fake/overseas.sock')
    assert client.get(OVERSEAS).status_code == 403
    monkeypatch.setattr(get_settings(), 'full_access_member_ids', frozenset({actor}))
    assert client.get(OVERSEAS).status_code == 200
    assert exchange[-1][0] == '/fake/overseas.sock'
    assert exchange[-1][1]['actor'] == {'id': str(actor), 'name': '海外成员'}
    assert client.get(ROOT).status_code == 404
    assert client.post(OVERSEAS + '/check').status_code == 403
    assert client.post(OVERSEAS + '/check', headers=HEADERS).status_code == 200
    monkeypatch.setattr(get_settings(), 'full_access_member_ids', frozenset())
    assert client.get(OVERSEAS).status_code == 403
    with factory.begin() as session:
        session.scalar(select(MemberRole).where(MemberRole.user_id == actor)).role = 'super_admin'
    assert client.get(OVERSEAS).status_code == 200
    with factory.begin() as session:
        session.get(Member, actor).status = 'disabled'
    assert client.get(OVERSEAS).status_code == 403
