import os

import pytest

from app.execution import managed_credentials as credentials
from app.execution import credential_broker_client as client
from test_managed_credentials import auth, read, write


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source, home = tmp_path / 'master' / 'auth.json', tmp_path / 'session' / 'home'
    home.mkdir(parents=True)
    control = home.parent / 'control'
    control.mkdir()
    write(source, auth())
    monkeypatch.setattr(credentials, '_request_refresh', lambda _: pytest.fail('unexpected refresh'))
    return source, home, home / '.codex' / 'auth.json', control


def sync(setup, **kwargs):
    source, home, _, control = setup
    credentials.sync_credentials(source, home, 600, control=control, **kwargs)


def test_new_session_creates_trusted_binding(setup):
    sync(setup)
    _, _, target, control = setup
    marker = control / 'auth-identity.json'
    assert read(marker) == {'mode': 'chatgpt', 'account': 'workspace-one', 'subject': 'user-one'}
    assert 'secret' not in marker.read_text()
    assert read(target)['tokens']['refresh_token'] == ''
    if os.name == 'posix':
        assert marker.stat().st_mode & 0o777 == 0o600
        assert control.stat().st_mode & 0o777 == 0o700


def test_old_session_without_private_or_binding_fails_closed(setup):
    with pytest.raises(credentials.CredentialsError):
        sync(setup, require_existing=True)
    assert not (setup[3] / 'auth-identity.json').exists()
    assert not setup[2].exists()


def test_old_session_migrates_expired_but_valid_identity(setup):
    write(setup[2], auth(ttl=-100))
    sync(setup, require_existing=True)
    assert (setup[3] / 'auth-identity.json').exists()


def test_old_session_migration_refuses_different_account(setup):
    write(setup[2], auth(account='old-workspace'))
    with pytest.raises(credentials.CredentialsError) as error:
        sync(setup, require_existing=True)
    assert error.value.code == 'credentials_account_changed'
    assert not (setup[3] / 'auth-identity.json').exists()


def test_trusted_binding_recovers_deleted_private_auth(setup):
    sync(setup)
    setup[2].unlink()
    sync(setup, require_existing=True)
    assert read(setup[2])['tokens']['account_id'] == 'workspace-one'


@pytest.mark.parametrize('replace_private', [False, True])
def test_deleted_or_rewritten_private_cannot_silently_change_account(setup, replace_private):
    sync(setup)
    setup[2].unlink()
    write(setup[0], auth(account='another-workspace'))
    if replace_private:
        write(setup[2], auth(account='another-workspace'))
    marker_before = (setup[3] / 'auth-identity.json').read_bytes()
    with pytest.raises(credentials.CredentialsError) as error:
        sync(setup, require_existing=True)
    assert error.value.code == 'credentials_account_changed'
    assert (setup[3] / 'auth-identity.json').read_bytes() == marker_before


def test_bound_session_ignores_valid_but_rewritten_private_identity(setup):
    sync(setup)
    write(setup[2], auth(account='untrusted-private'))
    sync(setup, require_existing=True)
    assert read(setup[2])['tokens']['account_id'] == 'workspace-one'


@pytest.mark.parametrize('where', ['home', 'work', 'rounds', 'parent'])
def test_binding_must_be_in_protected_control_sibling(setup, where):
    source, home, _, _ = setup
    bad = home if where == 'home' else home.parent / where
    bad.mkdir(exist_ok=True)
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(source, home, 600, control=bad)
    assert not (bad / 'auth-identity.json').exists()


@pytest.mark.parametrize('which', ['binding', 'directory', 'lock'])
def test_binding_symlinks_rejected(setup, which):
    _, home, _, control = setup
    other = home.parent / 'other'
    if which == 'directory':
        other.mkdir()
        control.rmdir()
        link, destination = control, other
    else:
        other.write_text('{}')
        link = control / ('auth-identity.json' if which == 'binding' else 'auth-identity.lock')
        destination = other
    try:
        link.symlink_to(destination, target_is_directory=which == 'directory')
    except OSError:
        pytest.skip('platform does not permit symlinks')
    with pytest.raises(credentials.CredentialsError):
        sync(setup)


@pytest.mark.parametrize('value', [{}, {'mode': 'chatgpt', 'account': '', 'subject': 'user'},
                                  {'mode': 'apikey', 'fingerprint': 'bad'}])
def test_corrupt_binding_refuses_recovery(setup, value):
    write(setup[3] / 'auth-identity.json', value)
    with pytest.raises(credentials.CredentialsError):
        sync(setup)


def test_api_key_binding_stores_only_digest_and_rejects_rotation(setup):
    write(setup[0], {'OPENAI_API_KEY': 'fake-private-key'})
    sync(setup)
    marker = setup[3] / 'auth-identity.json'
    assert 'fake-private-key' not in marker.read_text()
    assert len(read(marker)['fingerprint']) == 64
    setup[2].unlink()
    write(setup[0], {'OPENAI_API_KEY': 'other-fake-key'})
    with pytest.raises(credentials.CredentialsError):
        sync(setup, require_existing=True)


def test_broker_mode_never_reads_source(setup, monkeypatch):
    setup[0].unlink()
    value = auth()
    value['tokens']['refresh_token'] = ''
    calls = []
    def request(path, timeout):
        calls.append((path, timeout))
        return value
    monkeypatch.setattr(client, 'request_credentials', request)
    sync(setup, broker_socket='/run/test.sock')
    assert calls == [('/run/test.sock', 600)]
    assert read(setup[2]) == value


def test_require_existing_without_control_still_needs_evidence(setup):
    with pytest.raises(credentials.CredentialsError):
        credentials.sync_credentials(setup[0], setup[1], 600, require_existing=True)


def test_unexpected_master_fields_never_leave_central_store(setup):
    value = auth()
    value['secret_metadata'] = 'sensitive'
    value['tokens']['next_refresh_token'] = 'sensitive'
    write(setup[0], value)
    sync(setup)
    assert 'sensitive' not in setup[2].read_text()
    assert 'sensitive' in setup[0].read_text()
