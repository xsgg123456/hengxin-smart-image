import base64
import json
import io
import multiprocessing
import os
import subprocess
import time
import urllib.request
from types import SimpleNamespace

import pytest

from app.execution import managed_credentials as credentials
from app.execution import managed_credentials_files as files


def jwt(**claims):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return 'eyJhbGciOiJub25lIn0.' + payload + '.test-signature'


def auth(ttl=7200, account='workspace-one', subject='user-one'):
    claims = {'sub': subject, credentials.AUTH_CLAIM: {'chatgpt_account_id': account}}
    return {'auth_mode': 'chatgpt', 'OPENAI_API_KEY': None, 'tokens': {
        'id_token': jwt(**claims), 'access_token': jwt(**claims, exp=time.time() + ttl),
        'refresh_token': 'secret-refresh', 'account_id': account}, 'last_refresh': 'old'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source, home = tmp_path / 'master' / 'auth.json', tmp_path / 'private'
    home.mkdir()
    write(source, auth())
    monkeypatch.setattr(credentials, '_request_refresh', lambda token: pytest.fail('unexpected network'))
    return source, home, home / '.codex' / 'auth.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_sync_updates_old_session_and_removes_refresh(setup):
    source, home, target = setup
    write(target, auth(ttl=-100))
    before = source.read_bytes()
    credentials.sync_credentials(source, home, 600)
    assert source.read_bytes() == before
    expected = read(source)
    expected['tokens']['refresh_token'] = ''
    assert read(target) == expected
    if os.name == 'posix':
        assert source.stat().st_mode & 0o777 == target.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('ttl,expected_calls', [(899, 1), (901, 0), (-10, 1)])
def test_expiry_margin_refresh_once(setup, monkeypatch, ttl, expected_calls):
    source, home, target = setup
    write(source, auth(ttl=ttl))
    calls = []
    def refresh(token):
        calls.append(token)
        return {**auth()['tokens'], 'refresh_token': 'rotated-secret'}
    monkeypatch.setattr(credentials, '_request_refresh', refresh)
    credentials.sync_credentials(source, home, 600)
    credentials.sync_credentials(source, home, 600)
    assert len(calls) == expected_calls
    assert read(target)['tokens']['refresh_token'] == ''
    if calls:
        assert read(source)['tokens']['refresh_token'] == 'rotated-secret'
        assert read(source)['last_refresh'] != 'old'


def test_refresh_omitted_optional_tokens_preserves_main_refresh(setup, monkeypatch):
    source, home, _ = setup
    write(source, auth(ttl=1))
    monkeypatch.setattr(credentials, '_request_refresh', lambda _: {
        'access_token': auth()['tokens']['access_token']})
    credentials.sync_credentials(source, home, 600)
    assert read(source)['tokens']['refresh_token'] == 'secret-refresh'


@pytest.mark.parametrize('failure', ['network', 'short', 'missing', 'empty', 'badjwt', 'account', 'subject'])
def test_refresh_failure_is_atomic_and_sanitized(setup, monkeypatch, failure):
    source, home, target = setup
    write(source, auth(ttl=1))
    write(target, auth(ttl=-1))
    before = source.read_bytes(), target.read_bytes()
    def refresh(_):
        if failure == 'network':
            raise RuntimeError('secret-refresh internal-path')
        if failure == 'missing':
            return {}
        if failure == 'empty':
            return {'access_token': ''}
        if failure == 'badjwt':
            return {'access_token': 'secret-refresh'}
        return auth(ttl=1 if failure == 'short' else 7200,
                    account='other' if failure == 'account' else 'workspace-one',
                    subject='other' if failure == 'subject' else 'user-one')['tokens']
    monkeypatch.setattr(credentials, '_request_refresh', refresh)
    with pytest.raises(credentials.CredentialsError) as error:
        credentials.sync_credentials(source, home, 600)
    assert 'secret-refresh' not in str(error.value)
    assert 'internal-path' not in str(error.value)
    assert (source.read_bytes(), target.read_bytes()) == before


@pytest.mark.parametrize('change', ['account', 'subject', 'missing', 'id_claim', 'mode'])
def test_identity_change_rejected_before_refresh(setup, change):
    source, home, target = setup
    write(source, auth(ttl=-1))
    previous = auth(account='other' if change == 'account' else 'workspace-one',
                    subject='other' if change == 'subject' else 'user-one')
    if change == 'missing':
        previous['tokens'].pop('account_id')
    if change == 'id_claim':
        previous['tokens']['id_token'] = jwt(sub='user-one')
    if change == 'mode':
        previous = {'auth_mode': 'apikey', 'OPENAI_API_KEY': 'fake-key'}
    write(target, previous)
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)


def test_api_key_passthrough_and_rotation_fails_closed(setup):
    source, home, target = setup
    key_auth = {'auth_mode': 'apikey', 'OPENAI_API_KEY': 'fake-test-key'}
    write(source, key_auth)
    credentials.sync_credentials(source, home, 600)
    assert read(target) == key_auth
    write(source, {**key_auth, 'OPENAI_API_KEY': 'fake-other-key'})
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)


@pytest.mark.parametrize('invalid', [[], {}, {'auth_mode': 'external'}, {'tokens': {}},
                                    {'auth_mode': 'chatgptAuthTokens'}])
def test_unsupported_or_invalid_auth(setup, invalid):
    source, home, _ = setup
    write(source, invalid)
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)


@pytest.mark.parametrize('which', ['source', 'target', 'lock'])
@pytest.mark.parametrize('link', ['hard', 'symbolic', 'directory'])
def test_link_and_nonregular_files_rejected(setup, which, link):
    source, home, target = setup
    target.parent.mkdir(exist_ok=True)
    path = {'source': source, 'target': target, 'lock': source.with_name('auth.json.refresh.lock')}[which]
    original = source.read_bytes()
    other = home / 'other.json'
    other.write_bytes(original)
    path.unlink(missing_ok=True)
    try:
        if link == 'hard':
            os.link(other, path)
        elif link == 'symbolic':
            path.symlink_to(other)
        else:
            path.mkdir()
    except OSError:
        pytest.skip('platform does not permit symlinks')
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)
    assert other.read_bytes() == original


def test_target_directory_link_rejected(setup):
    source, home, target = setup
    other = home / 'other'
    other.mkdir()
    try:
        target.parent.symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip('platform does not permit directory symlinks')
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)
    assert not (other / 'auth.json').exists()


def test_atomic_replace_failure_keeps_main_auth(setup, monkeypatch):
    source, home, _ = setup
    write(source, auth(ttl=-1))
    before = source.read_bytes()
    monkeypatch.setattr(credentials, '_request_refresh', lambda _: auth()['tokens'])
    monkeypatch.setattr(files.os, 'replace', lambda *a, **kw: (_ for _ in ()).throw(OSError('secret')))
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)
    assert source.read_bytes() == before
    assert not list(source.parent.glob('.auth-*'))


def test_refresh_transport_bounded_and_secret_not_in_command(monkeypatch):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(stdout=b'{"access_token":"fake"}')
    monkeypatch.setattr(credentials.subprocess, 'run', run)
    assert credentials._request_refresh('private-refresh') == {'access_token': 'fake'}
    argv, options = calls[0]
    assert 'private-refresh' not in str(argv)
    assert options['timeout'] == 30 and options['check'] is True
    assert json.loads(options['input']) == {'client_id': credentials.CLIENT_ID,
        'grant_type': 'refresh_token', 'refresh_token': 'private-refresh'}


@pytest.mark.parametrize('kind', ['timeout', 'error', 'large', 'malformed'])
def test_transport_errors_are_sanitized(monkeypatch, kind):
    def run(*args, **kwargs):
        if kind == 'timeout':
            raise subprocess.TimeoutExpired('secret-refresh', 30)
        if kind == 'error':
            raise subprocess.CalledProcessError(1, 'secret-refresh', stderr='secret-refresh')
        return SimpleNamespace(stdout=b'x' * 131073 if kind == 'large' else b'not json secret-refresh')
    monkeypatch.setattr(credentials.subprocess, 'run', run)
    with pytest.raises(credentials.CredentialsError) as error:
        credentials._request_refresh('secret-refresh')
    assert error.value.code == 'credentials_refresh_failed'
    assert 'secret-refresh' not in str(error.value)


@pytest.mark.skipif(os.name != 'posix', reason='production POSIX flock test')
def test_concurrent_processes_refresh_exactly_once(setup, monkeypatch):
    source, home, _ = setup
    write(source, auth(ttl=-1))
    counter = home / 'refresh-count'
    def refresh(_):
        with counter.open('a') as stream:
            stream.write('refresh\n')
        time.sleep(0.2)
        return {**auth()['tokens'], 'refresh_token': 'rotated-secret'}
    monkeypatch.setattr(credentials, '_request_refresh', refresh)
    processes = []
    for index in range(4):
        private_home = home / str(index)
        private_home.mkdir()
        process = multiprocessing.get_context('fork').Process(
            target=credentials.sync_credentials, args=(source, private_home, 600))
        process.start()
        processes.append(process)
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    assert counter.read_text().splitlines() == ['refresh']
    for index in range(4):
        assert read(home / str(index) / '.codex' / 'auth.json')['tokens']['refresh_token'] == ''


def test_lock_wait_is_bounded_and_releases(setup):
    source, _, _ = setup
    with files.directory(source.parent) as folder:
        with files.refresh_lock(folder, 'test.lock'):
            with pytest.raises(TimeoutError):
                with files.refresh_lock(folder, 'test.lock', timeout=0):
                    pytest.fail('must not acquire held lock')
        with files.refresh_lock(folder, 'test.lock', timeout=0):
            pass


def test_urllib_helper_protocol_and_redirect_block(monkeypatch):
    import sys
    observed = []
    def build(handler):
        with pytest.raises(ValueError):
            handler.redirect_request(None, None, 307, '', {}, 'https://attacker.invalid')
        def open_request(request, timeout):
            observed.append((request, timeout))
            return io.BytesIO(b'{"access_token":"fake-token"}')
        return SimpleNamespace(open=open_request)
    output = io.BytesIO()
    monkeypatch.setattr(urllib.request, 'build_opener', build)
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(b'{"refresh_token":"fake"}')))
    monkeypatch.setattr(sys, 'stdout', SimpleNamespace(buffer=output))
    exec(credentials._REFRESH_SCRIPT, {})
    request, timeout = observed[0]
    assert request.full_url == credentials.TOKEN_ENDPOINT and timeout == 30
    assert request.get_method() == 'POST' and json.loads(request.data)['refresh_token'] == 'fake'
    assert output.getvalue() == b'{"access_token":"fake-token"}'


@pytest.mark.parametrize('exp', [None, True, '7200', float('inf')])
def test_malformed_access_expiry_rejected(setup, exp):
    source, home, _ = setup
    value = auth()
    claims = credentials._jwt(value['tokens']['access_token'])
    value['tokens']['access_token'] = jwt(**{**claims, 'exp': exp})
    write(source, value)
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600)
