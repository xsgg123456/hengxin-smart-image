import json
import threading
import time
from uuid import uuid4

import pytest

from app.account_management.manager import AccountManager
from app.account_management.store import AccountStore, AccountError
from app.execution.managed_credentials import sync_credentials, CredentialsError
from test_managed_credentials import auth, write, read

ACTOR = {'id': str(uuid4()), 'name': '测试管理员'}
OTHER = {'id': str(uuid4()), 'name': '另一个管理员'}


def wait_for(predicate):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('authorization state did not settle')


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / 'master' / 'auth.json'
    write(source, auth())
    managers = []
    def create(side, candidate=None, outcome='ready', login_ok=True):
        def login(home, binary, cancelled, publish, expires):
            publish('ABCD-EFGH')
            if candidate is not None:
                write(home / '.codex' / 'auth.json', candidate)
            return login_ok
        manager = AccountManager(AccountStore(tmp_path / side, source), 'test-cli', 'test-bwrap',
                                 login=login, verify=lambda *args: outcome)
        managers.append(manager)
        return manager
    yield source, create
    for manager in managers:
        manager.close()


def verified(manager, intent='renew'):
    pending = manager.start(ACTOR, intent, manager.status()['revision'])
    wait_for(lambda: manager.poll(ACTOR, pending['id'])['step'] in ('verified', 'mismatch', 'failed'))
    return manager.poll(ACTOR, pending['id'])


def test_legacy_is_referenced_and_not_copied(setup):
    source, create = setup
    domestic, overseas = create('domestic'), create('overseas')
    before = source.read_bytes()
    assert domestic.store.source() == overseas.store.source() == source
    assert domestic.status()['status'] == 'unchecked'
    assert not list(domestic.store.root.rglob('auth.json'))
    domestic.remove(ACTOR, 0)
    assert domestic.status()['status'] == 'empty'
    assert overseas.store.source() == source and source.read_bytes() == before
    assert 'secret-refresh' not in json.dumps(overseas.status())


def test_renew_preserves_two_original_session_homes_and_other_profile(setup, tmp_path):
    source, create = setup
    candidate = auth()
    candidate['tokens']['refresh_token'] = 'fresh-independent-grant'
    domestic, overseas = create('domestic', candidate), create('overseas')
    homes = [tmp_path / name for name in ('old-session-one', 'old-session-two')]
    for home in homes:
        home.mkdir()
        sync_credentials(source, home, 60)
        (home / 'history.json').write_text('original session history')
    before = source.read_bytes()
    pending = verified(domestic)
    domestic.activate(ACTOR, pending['id'], False)
    assert domestic.store.source() != source
    assert read(domestic.store.source())['tokens']['refresh_token'] == 'fresh-independent-grant'
    for home in homes:
        sync_credentials(domestic.store.source(), home, 60, require_existing=True)
        assert (home / 'history.json').read_text() == 'original session history'
        assert not read(home / '.codex' / 'auth.json')['tokens']['refresh_token']
    assert overseas.store.source() == source and source.read_bytes() == before


def test_wrong_account_renew_rejected_even_with_same_email(setup):
    source, create = setup
    manager = create('domestic', auth(account='different-workspace'))
    pending = verified(manager)
    assert pending['step'] == 'mismatch' and pending['different']
    with pytest.raises(AccountError):
        manager.activate(ACTOR, pending['id'], True)
    assert manager.store.source() == source


@pytest.mark.parametrize('intent', ['renew', 'replace'])
def test_external_identity_change_before_activation_requires_new_flow(setup, intent):
    source, create = setup
    manager = create('domestic', auth())
    pending = verified(manager, intent)
    assert not pending['different']
    write(source, auth(account='concurrently-changed'))
    with pytest.raises(AccountError, match='原账号身份已变化'):
        manager.activate(ACTOR, pending['id'], False)
    assert manager.status()['revision'] == 0
    assert read(source)['tokens']['account_id'] == 'concurrently-changed'


def test_replace_requires_confirmation_and_old_session_identity_still_enforced(setup, tmp_path):
    source, create = setup
    home = tmp_path / 'original-home'
    home.mkdir()
    sync_credentials(source, home, 60)
    manager = create('domestic', auth(account='new-workspace'))
    pending = verified(manager, 'replace')
    with pytest.raises(AccountError):
        manager.activate(ACTOR, pending['id'], False)
    assert manager.store.source() == source
    manager.activate(ACTOR, pending['id'], True)
    with pytest.raises(CredentialsError, match='账号或工作区已变更'):
        sync_credentials(manager.store.source(), home, 60, require_existing=True)


@pytest.mark.parametrize('login_ok,candidate,outcome', [
    (False, None, 'ready'), (True, auth(), 'network'), (True, auth(), 'expired')])
def test_failed_candidate_never_overwrites_existing(setup, login_ok, candidate, outcome):
    source, create = setup
    manager = create('domestic', candidate, outcome, login_ok)
    before = source.read_bytes()
    pending = verified(manager)
    assert pending['step'] == 'failed'
    with pytest.raises(AccountError):
        manager.activate(ACTOR, pending['id'], False)
    manager.cancel(ACTOR, pending['id'])
    wait_for(lambda: manager.pending is None)
    assert not list(manager.scratch.iterdir())
    assert source.read_bytes() == before and manager.status()['revision'] == 0


def test_retry_then_enable_and_audit_contains_no_credentials(setup):
    source, create = setup
    manager = create('domestic', auth(), 'network')
    pending = verified(manager)
    manager.verify = lambda *args: 'ready'
    manager.retry(ACTOR, pending['id'])
    wait_for(lambda: manager.poll(ACTOR, pending['id'])['step'] == 'verified')
    value = manager.activate(ACTOR, pending['id'], False)
    assert value['status'] == 'ready' and value['audit'][0]['operator'] == ACTOR['name']
    assert not any(secret in json.dumps(value) for secret in ('secret-refresh', 'ABCD-EFGH', 'test-signature'))


def test_owner_and_revision_guard(setup):
    source, create = setup
    manager = create('domestic', auth())
    pending = verified(manager)
    for operation in (manager.poll, manager.cancel, manager.retry):
        with pytest.raises(AccountError) as error:
            operation(OTHER, pending['id'])
        assert error.value.status == 403
    with pytest.raises(AccountError):
        manager.start(OTHER, 'renew', 0)
    manager.store.remove(0, OTHER)
    with pytest.raises(AccountError) as error:
        manager.activate(ACTOR, pending['id'], False)
    assert error.value.status == 409
    assert manager.status()['status'] == 'empty' and source.exists()


def test_expired_confirmation_and_duplicate_activation_refused(setup):
    source, create = setup
    manager = create('domestic', auth())
    pending = verified(manager)
    manager.pending['expiresAt'] = time.time() - 1
    with pytest.raises(AccountError):
        manager.activate(ACTOR, pending['id'], False)
    assert manager.store.source() == source


def test_expiry_cancels_probe_and_new_flow_waits_for_cleanup(setup):
    source, create = setup
    manager = create('domestic', auth())
    entered, stopped, release = threading.Event(), threading.Event(), threading.Event()
    def verify(source, root, binary, bwrap, cancelled):
        entered.set()
        wait_for(cancelled)
        stopped.set()
        release.wait(3)
        return 'network'
    manager.verify = verify
    pending = manager.start(ACTOR, 'renew', 0)
    assert entered.wait(2)
    manager.pending['expiresAt'] = time.time() - 1
    assert manager.poll(ACTOR, pending['id'])['step'] == 'expired'
    assert stopped.wait(2)
    with pytest.raises(AccountError, match='正在结束'):
        manager.start(ACTOR, 'renew', 0)
    release.set()
    wait_for(lambda: manager.pending.get('cleanupComplete'))
    assert not list(manager.scratch.iterdir())
    assert manager.store.source() == source
    manager.verify = lambda *args: 'ready'
    assert verified(manager)['id'] != pending['id']


def test_stale_connection_check_cannot_rewrite_removed_account(setup):
    source, create = setup
    manager = create('domestic')
    started, finish = threading.Event(), threading.Event()
    def probe(*args):
        started.set()
        finish.wait(3)
        return 'ready'
    manager.verify = probe
    assert manager.check(ACTOR)['checking']
    assert started.wait(2)
    manager.remove(ACTOR, 0)
    finish.set()
    wait_for(lambda: not manager.checking)
    assert manager.status()['status'] == 'empty'


def test_cancellation_stops_waiting_login_without_touching_master(setup):
    source, create = setup
    manager = create('domestic')
    def login(home, binary, cancelled, publish, expires):
        publish('ABCD-EFGH')
        wait_for(cancelled)
        return False
    manager.login = login
    pending = manager.start(ACTOR, 'renew', 0)
    manager.cancel(ACTOR, pending['id'])
    wait_for(lambda: manager.pending is None)
    assert manager.store.source() == source and not list(manager.scratch.iterdir())
