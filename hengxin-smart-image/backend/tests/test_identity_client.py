import json
import subprocess
import sys
from datetime import timedelta
from io import BytesIO
from urllib.error import HTTPError, URLError
import pytest
from fastapi import HTTPException
from app.identity import client
from app.identity.tokens import utcnow


def grant():
    return {'member': {'corp_id': 'corp', 'provider_user_id': 'user', 'union_id': None,
                       'name': '成员', 'department': ''},
            'identity_session_id': 'test-id',
            'expires_at': (utcnow() + timedelta(hours=1)).isoformat()}


def reply(monkeypatch, value):
    monkeypatch.setattr(client, 'urlopen', lambda request, timeout: BytesIO(json.dumps(value).encode()))


def test_remote_grants_require_valid_profile_aware_future_expiry(monkeypatch):
    valid = grant()
    reply(monkeypatch, valid)
    assert client.redeem_ticket('http://identity', 'test-key', 'ticket')['member']['name'] == '成员'
    invalid = [None, [], {}, valid | {'member': None}, valid | {'identity_session_id': ''},
               valid | {'expires_at': '2030-01-01T00:00:00'},
               valid | {'expires_at': (utcnow() - timedelta(seconds=1)).isoformat()},
               valid | {'member': valid['member'] | {'role': 'super_admin'}},
               valid | {'member': valid['member'] | {'provider_user_id': ' '}}]
    for item in invalid:
        reply(monkeypatch, item)
        with pytest.raises(HTTPException) as caught:
            client.redeem_ticket('http://identity', 'test-key', 'ticket')
        assert caught.value.status_code == 503


@pytest.mark.parametrize('error,status', [(URLError('secret'), 503),
    (HTTPError('http://identity', 500, 'secret', {}, None), 503),
    (HTTPError('http://identity', 401, 'secret', {}, None), 401)])
def test_remote_failures_fail_closed_without_provider_detail(monkeypatch, error, status):
    def fail(request, timeout):
        assert timeout == 3
        raise error
    monkeypatch.setattr(client, 'urlopen', fail)
    with pytest.raises(HTTPException) as caught:
        client.check_identity('http://identity', 'test-key', 'sid')
    assert caught.value.status_code == status
    assert 'secret' not in caught.value.detail


def test_check_requires_actual_boolean(monkeypatch):
    for value in (True, False):
        reply(monkeypatch, {'active': value})
        assert client.check_identity('http://identity', 'test-key', 'sid') is value
    for value in ('true', 1, None):
        reply(monkeypatch, {'active': value})
        with pytest.raises(HTTPException) as caught:
            client.check_identity('http://identity', 'test-key', 'sid')
        assert caught.value.status_code == 503


def test_identity_entry_does_not_load_domestic_orm_or_settings():
    source = '''
import os, sys
for key in list(os.environ):
    if key.startswith(('IDENTITY_', 'OVERSEAS_')) or key in ('DATABASE_URL', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY'):
        os.environ.pop(key)
import app.identity.main
assert 'app.models' not in sys.modules
assert 'app.resource_models' not in sys.modules
assert 'app.modules.auth.models' not in sys.modules
assert 'app.db.session' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
