"""Fault injection: drift/unknown work/migration/check failures must not reopen old code."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('member_deploy_tests', Path(__file__).with_name('member-release-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
m = d.m


@pytest.fixture(autouse=True)
def private_files_on_windows(monkeypatch):
    def save(path, value):
        Path(path).write_text(value if isinstance(value, str) else json.dumps(value))
    for runtime in (m, d.drain.m, d.backup.m, d.verify.m):
        monkeypatch.setattr(runtime, 'private', save)


def setup(monkeypatch, tmp_path, failure=None):
    work = tmp_path / 'work'
    work.mkdir()
    for name in ('PREPARED', 'INSTALL_TEST_IMAGE_ID'):
        (work / name).write_text('sha256:tested')
    data = {group: {'group': group} for group in m.GROUPS}
    (work / 'topology.json').write_text(json.dumps(data))
    (work / 'native-targets.json').write_text(json.dumps(dict(domestic='/new/domestic', overseas='/new/overseas')))
    edge = tmp_path / 'edge.conf'
    edge.write_text('original')
    events = []
    def event(name, *args):
        events.append((name, *args))
        if failure == name:
            raise RuntimeError(name)
    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backups')
    monkeypatch.setattr(m, 'APP', tmp_path)
    monkeypatch.setattr(m, 'EDGE', edge)
    monkeypatch.setattr(m, 'image_id', lambda *args: 'sha256:tested')
    monkeypatch.setattr(m, 'topology', lambda: data)
    monkeypatch.setattr(m, 'prepared_settings', lambda *args: None)
    monkeypatch.setattr(m, 'assets_safe', lambda *args: event('assets'))
    monkeypatch.setattr(m, 'closed_config', lambda body: body)
    monkeypatch.setattr(m, 'close_edge', lambda *args: event('close'))
    monkeypatch.setattr(m, 'stop_apis', lambda *args: event('stop_apis'))
    monkeypatch.setattr(m, 'run', lambda *args, **kwargs: event('run', *args))
    def compose(data, *args, **kwargs):
        name = ('migrate_' if args[0] == 'run' else 'start_') + data['group']
        event(name, *args)
    monkeypatch.setattr(m, 'compose', compose)
    monkeypatch.setattr(m.r, 'sql', lambda _: '0028' if any(e[0] == 'migrate_domestic' for e in events) else '0027')
    monkeypatch.setattr(m.u, 'sql', lambda _: 'overseas_0014' if any(e[0] == 'migrate_overseas' for e in events) else 'overseas_0013')
    monkeypatch.setattr(d.drain, 'drain_and_stop', lambda *args: event('drain'))
    def backup(work, dest, *args):
        event('backup')
        dest.mkdir(parents=True)
        (dest / 'COMPLETE').write_text('verified')
    monkeypatch.setattr(d.backup, 'create', backup)
    monkeypatch.setattr(d.backup, 'verify_after', lambda *args: event('invariants'))
    monkeypatch.setattr(m.r, 'switch_native', lambda *args: event('native_domestic'))
    monkeypatch.setattr(m.u, 'switch_native', lambda *args: event('native_overseas'))
    monkeypatch.setattr(m.r, 'publish', lambda *args: event('publish'))
    monkeypatch.setattr(m.u, 'reload_edge', lambda: event('open'))
    for name in ('installed', 'frontend', 'proxy', 'public', 'closed'):
        monkeypatch.setattr(d.verify, name, lambda *args, name=name: event(name))
    return work, data, events


@pytest.mark.parametrize('failure', ['closed', 'drain', 'backup', 'migrate_domestic', 'migrate_overseas',
    'invariants', 'native_domestic', 'native_overseas', 'start_identity', 'start_domestic', 'start_overseas',
    'installed', 'proxy', 'publish', 'frontend', 'open', 'public'])
def test_each_failure_closes_all_intake_without_rollback_or_executor_stop(monkeypatch, tmp_path, failure):
    work, _, events = setup(monkeypatch, tmp_path, failure)
    with pytest.raises(RuntimeError, match=failure):
        d.deploy(work, tmp_path, {'release': 'fixture'}, 'image')
    assert events[-2:] == [('close',), ('stop_apis',)]
    assert not any('downgrade' in str(e) or 'restore' in str(e) for e in events)
    assert not any(e[:3] == ('run', 'systemctl', 'stop') for e in events)
    assert not (work / 'verification.json').exists()


def test_success_orders_closed_drain_backup_migrate_invariants_all_checks_before_open(monkeypatch, tmp_path):
    work, _, events = setup(monkeypatch, tmp_path)
    d.deploy(work, tmp_path, {'release': 'fixture'}, 'image')
    names = [event[0] for event in events]
    order = ['close', 'stop_apis', 'drain', 'backup', 'migrate_domestic', 'migrate_overseas',
             'invariants', 'native_domestic', 'native_overseas', 'start_identity', 'start_domestic',
             'start_overseas', 'installed', 'proxy', 'publish', 'frontend', 'open', 'public']
    assert [names.index(name) for name in order] == sorted(names.index(name) for name in order)
    assert (work / 'verification.json').exists()
    assert all('--no-deps' in e for e in events if e[0].startswith(('migrate_', 'start_')))


def test_topology_drift_refuses_any_cutover(monkeypatch, tmp_path):
    work, _, events = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(m, 'topology', lambda: {'drift': True})
    with pytest.raises(AssertionError, match='drift'):
        d.deploy(work, tmp_path, {'release': 'fixture'}, 'image')
    assert not events


def test_prior_migration_attempt_cannot_be_replayed(monkeypatch, tmp_path):
    work, _, events = setup(monkeypatch, tmp_path)
    (work / 'MIGRATION_STARTED').write_text('attempted')
    with pytest.raises(AssertionError, match='forward recovery'):
        d.deploy(work, tmp_path, {'release': 'fixture'}, 'image')
    assert not events


def empty_worker():
    return {'states': [{'node': []}, {'node': []}, {'node': []}], 'queues': {'expected': 0}, 'unacked': 0}


@pytest.mark.parametrize('fault', ('active', 'reserved', 'scheduled', 'queued', 'unacked', 'unknown', 'multiple'))
def test_no_false_idle_on_busy_or_unavailable_worker(fault):
    worker = empty_worker()
    if fault in ('active', 'reserved', 'scheduled'):
        worker['states'][('active', 'reserved', 'scheduled').index(fault)]['node'] = [{'id': 'paid-work'}]
    elif fault == 'queued':
        worker['queues']['expected'] = 1
    elif fault == 'unacked':
        worker['unacked'] = 1
    elif fault == 'unknown':
        worker['states'][0] = None
    else:
        worker['states'][0]['unexpected-node'] = []
    if fault in ('unknown', 'multiple'):
        with pytest.raises(AssertionError):
            d.drain.idle({'worker': worker})
    else:
        assert not d.drain.idle({'worker': worker})


@pytest.mark.parametrize('fault', ('domestic', 'overseas', 'variants', 'broker'))
def test_pending_timeout_keeps_executors_and_outboxes_running(monkeypatch, tmp_path, fault):
    result = dict(workers={'worker': empty_worker()}, domestic=0, overseas=0, variants=0)
    if fault == 'broker':
        result['workers']['worker']['queues']['expected'] = 1
    else:
        result[fault] = 1
    monkeypatch.setattr(d.drain, 'evidence', lambda *args: result)
    monkeypatch.setattr(d.drain.m, 'run', lambda *args: pytest.fail('May not stop anything while draining'))
    with pytest.raises(RuntimeError, match='executors remain running'):
        d.drain.wait_empty(tmp_path, 'fixture', timeout=0)


def test_publication_after_first_drain_is_rechecked_before_executor_stop(monkeypatch, tmp_path):
    events = []
    dm = d.drain.m
    def wait(work, label):
        events.append(label)
        if label == 'drained-after-outbox-stop':
            raise RuntimeError('late broker message')
    monkeypatch.setattr(d.drain, 'wait_empty', wait)
    monkeypatch.setattr(dm, 'compose', lambda *args: events.append(args))
    monkeypatch.setattr(dm, 'run', lambda *args: events.append(args))
    monkeypatch.setattr(dm.r, 'worker', lambda *args: pytest.fail('Executors not proven idle'))
    with pytest.raises(RuntimeError, match='late broker'):
        d.drain.drain_and_stop(tmp_path, tmp_path, {'domestic': {}})
    assert events[0] == 'drained-before-outbox-stop'
    assert ('systemctl', 'stop', dm.UNITS[2]) in events
    assert ('systemctl', 'stop', dm.UNITS[1]) not in events


def test_business_fingerprints_reject_deleted_or_edited_member_and_nonempty_applications():
    b = d.backup
    before = {'users': '28:hash', 'roles': '25:hash', 'files': '100:hash'}
    after = {**before, **{name: '0:empty' for name in b.ADDED['domestic']}}
    b.compare(before, after, 'domestic')
    for table in ('users', 'roles', 'files', 'domestic_membership_applications'):
        changed = dict(after, **{table: '1:unexpected'})
        with pytest.raises(AssertionError):
            b.compare(before, changed, 'domestic')
    with pytest.raises(AssertionError):
        b.compare(before, {k: v for k, v in after.items() if k != 'users'}, 'domestic')


def test_backup_failure_never_marks_complete(monkeypatch, tmp_path):
    b = d.backup
    (tmp_path / 'EXECUTORS_STOPPED').write_text('idle')
    monkeypatch.setattr(b, 'backup_config', lambda *args: None)
    monkeypatch.setattr(b, 'fingerprint', lambda *args: {'users': '28:hash'})
    monkeypatch.setattr(b, 'dump', lambda *args: None)
    def bad_restore(*args):
        raise RuntimeError('restored fingerprint mismatch')
    monkeypatch.setattr(b, 'restore_check', bad_restore)
    with pytest.raises(RuntimeError, match='fingerprint mismatch'):
        b.create(tmp_path, tmp_path / 'backup', {}, 'fixture')
    assert not (tmp_path / 'backup/COMPLETE').exists()


def test_probe_has_all_states_and_broker_keys_without_consumer_mutation():
    code = d.drain.PROBE.format(module='app.worker.celery_app', queues=['celery'])
    compile(code, '<worker-probe>', 'exec')
    assert all(name in code for name in ('i.active()', 'i.reserved()', 'i.scheduled()', 'priority_steps', 'unacked_key'))
    assert 'cancel_consumer' not in code and 'add_consumer' not in code
