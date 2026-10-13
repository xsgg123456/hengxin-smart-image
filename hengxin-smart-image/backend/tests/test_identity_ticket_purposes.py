"""A read-only permission ticket cannot authorize a membership mutation."""
from concurrent.futures import ThreadPoolExecutor
import pytest

from app.identity import client as identity_client
from app.identity.tokens import hash_token
from test_identity_service import (
    HEADERS, PATH, DOMESTIC_KEY, OVERSEAS_KEY, identity, login, ticket, redeem,
)
from test_identity_client import grant


@pytest.mark.parametrize('purpose', ['access', 'session', 'application'])
@pytest.mark.parametrize('business,key', [('domestic', DOMESTIC_KEY), ('overseas', OVERSEAS_KEY)])
def test_purpose_and_business_are_both_bound(identity, purpose, business, key):
    client, store, redis, prefix = identity
    token = login(client)
    value = ticket(client, business, purpose)
    other_key = OVERSEAS_KEY if key == DOMESTIC_KEY else DOMESTIC_KEY
    assert redeem(client, value, other_key, purpose).status_code == 401
    for different in {'access', 'session', 'application'} - {purpose}:
        assert redeem(client, value, key, different).status_code == 401
    # Wrong purpose or audience must not consume the ticket from its valid namespace.
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: redeem(client, value, key, purpose), range(4)))
    assert sorted(response.status_code for response in responses) == [200, 401, 401, 401]
    assertion = next(response.json() for response in responses if response.status_code == 200)
    assert assertion['identity_session_id'] == store.resolve(token)['identity_session_id']
    assert len(list(redis.scan_iter(prefix + 'session:*'))) == 1


def test_old_unscoped_ticket_cannot_be_used_for_any_operation(identity):
    client, store, redis, prefix = identity
    token = login(client)
    value = 'pre-upgrade-ticket'
    redis.set(prefix + 'ticket:domestic:' + hash_token(value),
              store.resolve(token)['identity_session_id'], ex=60)
    for purpose in ('access', 'session', 'application'):
        assert redeem(client, value, purpose=purpose).status_code == 401


def test_default_ticket_is_session_only(identity):
    client, *_ = identity
    login(client)
    response = client.post(PATH + '/tickets', json={'business': 'domestic'}, headers=HEADERS)
    value = response.json()['ticket']
    assert redeem(client, value, purpose='application').status_code == 401
    assert redeem(client, value, purpose='access').status_code == 401
    assert redeem(client, value).status_code == 200


@pytest.mark.parametrize('body', [
    {'business': 'domestic', 'purpose': 'admin'},
    {'business': 'domestic', 'purpose': None},
    {'business': 'domestic', 'purpose': 'access', 'role': 'super_admin'},
])
def test_invalid_ticket_purpose_cannot_be_silently_ignored(identity, body):
    client, *_ = identity
    login(client)
    assert client.post(PATH + '/tickets', json=body, headers=HEADERS).status_code == 422
    assert client.post('/internal/redeem', json={'ticket': 'x', 'purpose': 'invalid'},
                       headers={'X-HX-Service-Key': DOMESTIC_KEY}).status_code == 422


def test_new_identity_session_is_detectable_even_if_name_is_unchanged(identity):
    client, *_ = identity
    login(client)
    before = client.get(PATH + '/me').json()
    login(client)
    after = client.get(PATH + '/me').json()
    assert before['name'] == after['name']
    assert before['sessionId'] != after['sessionId']
    assert after['sessionId'] != client.cookies.get('hx_identity')


@pytest.mark.parametrize('purpose', ['access', 'session', 'application'])
def test_client_forwards_only_server_selected_purpose(monkeypatch, purpose):
    calls = []

    def post(url, key, path, body):
        calls.append((path, body))
        return grant()

    monkeypatch.setattr(identity_client, '_post', post)
    assert identity_client.redeem_ticket('http://identity.test', 'key', 'opaque', purpose)
    assert calls == [('redeem', {'ticket': 'opaque', 'purpose': purpose})]


@pytest.mark.parametrize('purpose', ['access', 'session', 'application'])
def test_ticket_issuance_checks_confirmed_session_before_any_ticket_is_created(identity, purpose):
    client, store, redis, prefix = identity
    original = login(client)
    confirmed = store.resolve(original)['identity_session_id']
    body = {'business': 'overseas', 'purpose': purpose, 'expectedSessionId': confirmed}
    issued = client.post(PATH + '/tickets', json=body, headers=HEADERS)
    assert issued.status_code == 200
    old_ticket = issued.json()['ticket']
    login(client)  # Same display name, different authenticated session.
    before = {key: redis.get(key) for key in redis.scan_iter(prefix + 'ticket:*')}
    denied = client.post(PATH + '/tickets', json=body, headers=HEADERS)
    assert denied.status_code == 401
    assert before == {key: redis.get(key) for key in redis.scan_iter(prefix + 'ticket:*')}
    assert redeem(client, old_ticket, OVERSEAS_KEY, purpose).status_code == 401
    body['expectedSessionId'] = client.get(PATH + '/me').json()['sessionId']
    fresh = client.post(PATH + '/tickets', json=body, headers=HEADERS)
    assert fresh.status_code == 200
    grant = redeem(client, fresh.json()['ticket'], OVERSEAS_KEY, purpose)
    assert grant.status_code == 200
    assert grant.json()['identity_session_id'] == body['expectedSessionId']
