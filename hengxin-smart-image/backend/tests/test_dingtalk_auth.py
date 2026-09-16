from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.models import utcnow
from app.modules.auth import dingtalk
from app.modules.auth.models import UserIdentityRecord
from app.resource_models import UserRecord
from files_helpers import files_env
from urllib.parse import parse_qs, urlsplit


def provider_settings(**overrides):
    values = {
        'database_url': 'postgresql+psycopg://test:test@localhost/test',
        'minio_access_key': 'test-access',
        'minio_secret_key': 'test-secret',
        'dingtalk_corp_id': 'corp-1',
        'dingtalk_client_id': 'client-1',
        'dingtalk_agent_id': 'agent-1',
        'dingtalk_client_secret': 'secret-1',
        'dingtalk_callback_domain': 'https://image.example.com',
    }
    values.update(overrides)
    return Settings(**values)


def test_dingtalk_configuration_must_be_complete():
    with pytest.raises(ValueError, match='complete'):
        provider_settings(dingtalk_client_secret='')


def test_browser_authorize_url_contains_callback_and_one_time_state():
    settings = provider_settings()
    url = dingtalk.browser_authorize_url('state-value', settings)
    assert 'https://login.dingtalk.com/oauth2/auth?' in url
    assert 'client_id=client-1' in url
    assert 'scope=openid+corpid' in url
    assert 'state=state-value' in url
    assert 'redirect_uri=https%3A%2F%2Fimage.example.com%2Fapi%2Fv1%2Fauth%2Fdingtalk%2Fcallback' in url


def test_return_path_rejects_external_redirects():
    assert dingtalk.safe_return_path('https://attacker.example') == '/image-processing/wallpaper'
    assert dingtalk.safe_return_path('//attacker.example') == '/image-processing/wallpaper'
    assert dingtalk.safe_return_path('/tasks/index?task=abc') == '/tasks/index?task=abc'


def test_login_state_is_one_time_and_expires(files_env):
    _, factory, _, _ = files_env
    with factory.begin() as session:
        state = dingtalk.create_login_state(session, '/tasks/index')
        assert dingtalk.consume_login_state(session, state) == '/tasks/index'
        with pytest.raises(HTTPException, match='无效或已过期'):
            dingtalk.consume_login_state(session, state)
    with factory.begin() as session:
        expired = dingtalk.AuthLoginStateRecord(
            state_hash=dingtalk._hash_state('expired-state'), return_path='/tasks/index',
            expires_at=utcnow() - timedelta(minutes=1),
        )
        session.add(expired)
        session.flush()
        with pytest.raises(HTTPException, match='无效或已过期'):
            dingtalk.consume_login_state(session, 'expired-state')


def test_exchange_auth_code_maps_profile_and_rejects_other_enterprise(monkeypatch):
    settings = provider_settings()
    responses = [
        {'accessToken': 'access-token', 'corpId': 'corp-1'},
        {'openId': 'not-enterprise-id', 'nick': '张三', 'unionId': 'union-1', 'department': '设计部'},
        {'accessToken': 'app-token'},
        {'errcode': 0, 'result': {'userid': 'member-1', 'contact_type': 0}},
        {'errcode': 0, 'result': {'userid': 'member-1', 'unionid': 'union-1', 'name': '张三'}},
    ]
    def request(url, *args, **kwargs):
        if url.endswith('/users/me'):
            assert kwargs['headers'] == {'x-acs-dingtalk-access-token': 'access-token'}
        return responses.pop(0)
    monkeypatch.setattr(dingtalk, '_request_json', request)
    member = dingtalk.exchange_auth_code('one-time-code', settings)
    assert (member.provider_user_id, member.name, member.union_id, member.department) == (
        'member-1', '张三', 'union-1', '设计部',
    )

    responses[:] = [
        {'accessToken': 'access-token', 'corpId': 'other-corp'},
        {'unionId': 'union-1'},
    ]
    with pytest.raises(dingtalk.DingTalkEnterpriseMismatch):
        dingtalk.exchange_auth_code('one-time-code', settings)


def test_new_member_is_pending_and_does_not_receive_a_session(files_env, monkeypatch):
    _, factory, _, _ = files_env
    settings = provider_settings(dingtalk_admin_user_id='admin-member')
    monkeypatch.setattr(dingtalk, 'get_settings', lambda: settings)
    member = dingtalk.DingTalkMember('ordinary-member', '普通成员', 'union-2', '运营部', 'corp-1')
    with factory.begin() as session:
        with pytest.raises(dingtalk.DingTalkAccountError) as error:
            dingtalk.authenticate_member(session, member)
        assert error.value.code == 'AUTH_PENDING'
        assert session.query(UserRecord).filter_by(identity_source='dingtalk').count() == 1


def test_configured_admin_member_is_activated_without_first_login_promotion(files_env, monkeypatch):
    _, factory, _, _ = files_env
    settings = provider_settings(
        dingtalk_admin_user_id='', dingtalk_admin_user_ids='admin-member,second-admin',
    )
    monkeypatch.setattr(dingtalk, 'get_settings', lambda: settings)
    member = dingtalk.DingTalkMember('admin-member', '管理员', None, '', 'corp-1')
    with factory.begin() as session:
        user, token = dingtalk.authenticate_member(session, member)
        assert token
        assert (user.role, user.status) == ('super_admin', 'active')
        identity = session.query(UserIdentityRecord).filter_by(provider_user_id='admin-member').one()
        assert identity.corp_id == 'corp-1'


def test_each_configured_initial_admin_is_activated(files_env, monkeypatch):
    _, factory, _, _ = files_env
    settings = provider_settings(
        dingtalk_admin_user_id='', dingtalk_admin_user_ids='admin-member,second-admin',
    )
    monkeypatch.setattr(dingtalk, 'get_settings', lambda: settings)
    with factory.begin() as session:
        first, first_token = dingtalk.authenticate_member(
            session, dingtalk.DingTalkMember('admin-member', '吴永杰', None, '', 'corp-1'),
        )
        second, second_token = dingtalk.authenticate_member(
            session, dingtalk.DingTalkMember('second-admin', '张帅', None, '', 'corp-1'),
        )
        assert first_token and second_token
        assert (first.role, first.status, second.role, second.status) == (
            'super_admin', 'active', 'super_admin', 'active',
        )


@pytest.mark.parametrize('outcome', ['success', 'provider', 'enterprise', 'pending'])
def test_browser_callback_binding_and_failed_state_replay(files_env, monkeypatch, outcome):
    client, factory, _, _ = files_env
    monkeypatch.setattr(dingtalk, 'get_settings', lambda: provider_settings(
        dingtalk_admin_user_id='admin-member',
    ))
    calls = []

    def exchange(code):
        calls.append(code)
        if outcome == 'provider':
            raise dingtalk.DingTalkProviderError('test failure')
        if outcome == 'enterprise':
            raise dingtalk.DingTalkEnterpriseMismatch()
        member_id = 'ordinary-member' if outcome == 'pending' else 'admin-member'
        return dingtalk.DingTalkMember(member_id, '测试成员', None, '', 'corp-1')

    monkeypatch.setattr(dingtalk, 'exchange_auth_code', exchange)
    response = client.get('/api/v1/auth/dingtalk/authorize', follow_redirects=False)
    assert response.status_code == 303
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    path = '/api/v1/auth/dingtalk/callback'
    client.cookies.clear()
    for headers in ({}, {'cookie': 'hx_dingtalk_login_state=wrong-browser'}):
        denied = client.get(path, params={'state': state, 'code': 'code'},
                            headers=headers, follow_redirects=False)
        assert 'auth=denied' in denied.headers['location']
        assert not calls
    with factory() as session:
        assert session.query(dingtalk.AuthLoginStateRecord).one().consumed_at is None
    headers = {'cookie': f'hx_dingtalk_login_state={state}'}
    result = client.get(path, params={'state': state, 'code': 'code'},
                        headers=headers, follow_redirects=False)
    assert result.status_code == 303
    expected = {'provider': 'unavailable', 'enterprise': 'enterprise-mismatch', 'pending': 'AUTH_PENDING'}
    if outcome == 'success':
        assert 'auth=' not in result.headers['location']
        assert any('HttpOnly' in value for value in result.headers.get_list('set-cookie'))
    else:
        assert f'auth={expected[outcome]}' in result.headers['location']
    assert 'Max-Age=0' in result.headers.get_list('set-cookie')[0]
    with factory() as session:
        assert session.query(dingtalk.AuthLoginStateRecord).one().consumed_at is not None
    replay = client.get(path, params={'state': state, 'code': 'code'},
                        headers=headers, follow_redirects=False)
    assert 'auth=denied' in replay.headers['location']
    assert calls == ['code']


def test_container_code_uses_getuserinfo_not_oauth_user_token(monkeypatch):
    settings = provider_settings()
    urls = []

    def request(url, method='GET', body=None, headers=None):
        urls.append((url, method, body))
        if url.endswith('/oauth2/accessToken'):
            return {'accessToken': 'app-token'}
        if 'topapi/v2/user/getuserinfo' in url:
            assert body == {'code': 'jsapi-code'}
            return {'errcode': 0, 'result': {
                'userid': 'member-1', 'unionid': 'union-1', 'name': '张三',
            }}
        if 'topapi/v2/user/get?' in url:
            assert body == {'userid': 'member-1'}
            return {'errcode': 0, 'result': {
                'userid': 'member-1', 'unionid': 'union-1', 'name': '张三',
            }}
        raise AssertionError(url)

    monkeypatch.setattr(dingtalk, '_request_json', request)
    member = dingtalk.exchange_container_code('jsapi-code', settings)
    assert (member.provider_user_id, member.name, member.union_id, member.corp_id) == (
        'member-1', '张三', 'union-1', 'corp-1',
    )
    assert all('/oauth2/userAccessToken' not in url for url, *_ in urls)
    assert all('/contact/users/me' not in url for url, *_ in urls)
    assert any('getuserinfo' in url for url, *_ in urls)


def test_container_login_uses_jsapi_code_exchange(files_env, monkeypatch):
    client, _, _, _ = files_env
    monkeypatch.setattr(dingtalk, 'get_settings', lambda: provider_settings(
        dingtalk_admin_user_id='admin-member',
    ))
    calls = []

    def exchange(code):
        calls.append(code)
        return dingtalk.DingTalkMember('admin-member', '管理员', 'union-1', '', 'corp-1')

    monkeypatch.setattr(dingtalk, 'exchange_container_code', exchange)
    response = client.post('/api/v1/auth/dingtalk/container', json={'code': 'jsapi-code'})
    assert response.status_code == 200
    assert response.json()['name'] == '管理员'
    assert calls == ['jsapi-code']
    assert any('HttpOnly' in value for value in response.headers.get_list('set-cookie'))
