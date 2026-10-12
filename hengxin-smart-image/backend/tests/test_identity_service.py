"""Protocol tests run against explicitly configured disposable Redis only."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
import pytest
from fastapi.testclient import TestClient
from redis import Redis
from app.identity.config import IdentitySettings
from app.identity.main import create_app
from app.identity.store import PREFIX
from app.identity.tokens import hash_token, utcnow
from app.modules.auth import dingtalk

DOMESTIC_KEY = 'identity-domestic-test-key-0123456789abcdef'
OVERSEAS_KEY = 'identity-overseas-test-key-0123456789abcdef'
HEADERS = {'X-HX-Request': '1'}
PATH = '/api/identity/v1'


def settings(**overrides):
    values = dict(redis_url='redis://localhost:6379/15', public_origin='https://testserver',
                  domestic_service_key=DOMESTIC_KEY, overseas_service_key=OVERSEAS_KEY,
                  dingtalk_corp_id='corp-test', dingtalk_client_id='client-test',
                  dingtalk_agent_id='agent-test', dingtalk_client_secret='provider-test-secret')
    return IdentitySettings(**(values | overrides))


@pytest.fixture
def identity(monkeypatch):
    url = os.environ.get('TEST_IDENTITY_REDIS_URL')
    if not url:
        pytest.skip('requires explicitly disposable TEST_IDENTITY_REDIS_URL')
    redis = Redis.from_url(url, decode_responses=True)
    redis.ping()
    # Unique test keyspace; do not flush databases or touch other workers' keys.
    from uuid import uuid4
    prefix = PREFIX + uuid4().hex + ':'
    monkeypatch.setattr('app.identity.store.PREFIX', prefix)
    config = settings(redis_url=url)
    member = dingtalk.DingTalkMember('provider-1', '测试成员', 'union-1', '设计', 'corp-test')
    monkeypatch.setattr(dingtalk, 'exchange_container_code', lambda code, config: member)
    monkeypatch.setattr(dingtalk, 'exchange_auth_code', lambda code, config: member)
    app = create_app(config, redis)
    with TestClient(app, base_url='https://testserver') as client:
        yield client, app.state.store, redis, prefix
    keys = list(redis.scan_iter(prefix + '*'))
    if keys:
        redis.delete(*keys)
    redis.close()


def login(client):
    response = client.post(PATH + '/dingtalk/container', json={'code': 'test'}, headers=HEADERS)
    assert response.status_code == 200
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert 'Path=/api/identity/v1' in cookie
    return client.cookies.get('hx_identity')


def ticket(client, business='domestic'):
    response = client.post(PATH + '/tickets', json={'business': business}, headers=HEADERS)
    assert response.status_code == 200
    return response.json()['ticket']


def redeem(client, token, key=DOMESTIC_KEY):
    return client.post('/internal/redeem', json={'ticket': token}, headers={'X-HX-Service-Key': key})


def test_ticket_is_bound_atomic_and_only_hashes_persist(identity):
    client, store, redis, prefix = identity
    token = login(client)
    grant = ticket(client)
    assert redeem(client, grant, OVERSEAS_KEY).status_code == 401
    assert redeem(client, grant + 'tampered').status_code == 401
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: redeem(client, grant), range(8)))
    assert sorted(r.status_code for r in responses) == [200] + [401] * 7
    record = next(r.json() for r in responses if r.status_code == 200)
    assert record['member']['provider_user_id'] == 'provider-1'
    assert record['identity_session_id'] != token
    for key in redis.scan_iter(prefix + '*'):
        raw = redis.get(key)
        assert token not in key + raw and grant not in key + raw
    assert client.get(PATH + '/me').json() == {'name': '测试成员'}


def test_global_logout_invalidates_issued_grants_and_check(identity):
    client, store, redis, prefix = identity
    login(client)
    first = redeem(client, ticket(client)).json()
    unused = ticket(client, 'overseas')
    body = {'identity_session_id': first['identity_session_id']}
    headers = {'X-HX-Service-Key': OVERSEAS_KEY}
    assert client.post('/internal/check', json=body, headers=headers).json() == {'active': True}
    assert client.post(PATH + '/logout', headers=HEADERS).status_code == 204
    assert redeem(client, unused, OVERSEAS_KEY).status_code == 401
    assert client.post('/internal/check', json=body, headers=headers).json() == {'active': False}
    assert client.get(PATH + '/me').status_code == 401


def test_expiration_and_service_auth_fail_closed(identity):
    client, store, redis, prefix = identity
    token = login(client)
    grant = ticket(client)
    assert 0 < redis.ttl(prefix + 'ticket:domestic:' + hash_token(grant)) <= 60
    redis.delete(prefix + 'ticket:domestic:' + hash_token(grant))
    assert redeem(client, grant).status_code == 401
    record = store.resolve(token)
    record['expires_at'] = (utcnow() - timedelta(seconds=1)).isoformat()
    redis.set(prefix + 'session:' + record['identity_session_id'], json.dumps(record))
    assert client.get(PATH + '/me').status_code == 401
    assert client.post('/internal/check', json={'identity_session_id': 'x'}).status_code == 401
    assert client.post(PATH + '/tickets', json={'business': 'domestic'}, headers=HEADERS).status_code == 401


def test_oauth_binding_consumes_failed_state_and_rejects_replay(identity, monkeypatch):
    client, store, redis, prefix = identity
    auth = client.get(PATH + '/dingtalk/authorize', follow_redirects=False)
    state = parse_qs(urlsplit(auth.headers['location']).query)['state'][0]
    assert '/api/identity/v1/dingtalk/callback' in parse_qs(urlsplit(auth.headers['location']).query)['redirect_uri'][0]
    other = TestClient(client.app, base_url='https://testserver')
    assert other.get(PATH + '/dingtalk/callback', params={'state': state, 'code': 'x'}).status_code == 400
    def failure(*args):
        raise dingtalk.DingTalkProviderError('do not expose provider body')
    monkeypatch.setattr(dingtalk, 'exchange_auth_code', failure)
    response = client.get(PATH + '/dingtalk/callback', params={'state': state, 'code': 'x'}, follow_redirects=False)
    assert response.status_code == 303 and 'provider_error' in response.headers['location']
    client.cookies.set('hx_identity_state', state, domain='testserver.local', path=PATH)
    assert client.get(PATH + '/dingtalk/callback', params={'state': state, 'code': 'x'}).status_code == 400


def test_same_origin_required_no_cors_and_redis_failure(identity, monkeypatch):
    client, store, redis, prefix = identity
    assert client.post(PATH + '/dingtalk/container', json={'code': 'x'}).status_code == 403
    response = client.post(PATH + '/dingtalk/container', json={'code': 'x'},
                           headers=HEADERS | {'Origin': 'https://evil.example'})
    assert response.status_code == 403
    assert 'access-control-allow-origin' not in response.headers
    login(client)
    from redis.exceptions import ConnectionError
    def fail(*args):
        raise ConnectionError('sensitive dependency detail')
    monkeypatch.setattr(redis, 'get', fail)
    response = client.get(PATH + '/me')
    assert response.status_code == 503 and 'sensitive' not in response.text


def test_config_is_independent_and_rejects_weak_shared_keys(monkeypatch):
    for key in ('DATABASE_URL', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY'):
        monkeypatch.delenv(key, raising=False)
    assert settings().public_origin == 'https://testserver'
    for overrides in ({'overseas_service_key': DOMESTIC_KEY}, {'domestic_service_key': 'short'},
                      {'public_origin': 'https://testserver/path'}):
        with pytest.raises(ValueError):
            settings(**overrides)


def test_oauth_success_is_business_neutral_and_login_rotates_identity(identity):
    client, store, redis, prefix = identity
    old = login(client)
    old_sid = store.resolve(old)['identity_session_id']
    auth = client.get(PATH + '/dingtalk/authorize', follow_redirects=False)
    state = parse_qs(urlsplit(auth.headers['location']).query)['state'][0]
    response = client.get(PATH + '/dingtalk/callback', params={'state': state, 'authCode': 'x'},
                          follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == 'https://testserver/#/auth/business'
    assert store.by_id(old_sid) is None
    assert client.get(PATH + '/me').status_code == 200
    assert client.cookies.get('hx_identity') != old


def test_redis_ttl_expiration_rejects_ticket_and_session(identity):
    import time
    client, store, redis, prefix = identity
    token = login(client)
    record = store.resolve(token)
    grant = ticket(client)
    redis.pexpire(prefix + 'ticket:domestic:' + hash_token(grant), 1)
    redis.pexpire(prefix + 'session:' + record['identity_session_id'], 1)
    time.sleep(.02)
    assert redeem(client, grant).status_code == 401
    assert client.get(PATH + '/me').status_code == 401
    response = client.post('/internal/check',
                           json={'identity_session_id': record['identity_session_id']},
                           headers={'X-HX-Service-Key': DOMESTIC_KEY})
    assert response.json() == {'active': False}
