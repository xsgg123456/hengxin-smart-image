"""Joint release orchestration and interrupted-ledger recovery, without production I/O."""
from contextlib import nullcontext
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

import catalog
import engine
import joint_studio_engine
import joint_studio_forward
import joint_studio_marker
import joint_studio_packages
import joint_studio_paths
import joint_studio_release
import operations
import release
import scope_catalog
import scope_snapshot
import scopes
import snapshot
from test_scope_flow import world

REAL_FENCE_HOLD = joint_studio_release.fence.hold


@pytest.fixture
def upgrade(world, monkeypatch):
    w = world
    current = w.tool.load()
    current['current']['schema'] = {'domestic': '0032', 'overseas': 'overseas_0026'}
    current['current']['asset_fallbacks'] = {
        s: {'source': current['current']['groups'][s]['frontend']} for s in scopes.GROUPS}
    roots = {s: w.make('joint-' + s, s) for s in scopes.GROUPS}
    for s in scopes.GROUPS:
        current['groups'][s]['current'] = scope_snapshot.group(current['current'], s)
        current['retention']['staged'][str(roots[s])] = '/archive-' + s
    scope_catalog.seal(current)
    w.tool.save(current)
    state = {'runtime': copy.deepcopy(current['current']), 'schema': copy.deepcopy(current['current']['schema']),
             'fail_apply': None, 'actions': [], 'accepting': False, 'gateway_events': []}
    after = copy.deepcopy(state['runtime'])
    after['schema']['domestic'] = '0043'
    after['images'][scopes.DOMESTIC_PUBLISHER] = after['images']['domestic-api']
    for s in scopes.GROUPS:
        after['groups'][s]['backend'] = str(roots['domestic'])
        after['groups'][s]['frontend'] = str(roots[s])
        after['asset_fallbacks'][s]['source'] = current['current']['groups'][s]['frontend']
    state['after'] = after
    w.u.SYSTEMD = w.store.root / 'systemd'
    w.u.DROPIN = '90-unified-source.conf'
    w.u.contexts = lambda: {}
    monkeypatch.setattr(release.Release, 'capture', lambda self, data, runtime=False: copy.deepcopy(state['runtime']))
    monkeypatch.setattr(scope_snapshot, 'capture', lambda *args, **kwargs: copy.deepcopy(state['runtime']))
    monkeypatch.setattr(snapshot, 'schemas', lambda u: state['schema'].copy())
    monkeypatch.setattr(catalog, 'before', lambda u, store, data: data)
    monkeypatch.setattr(joint_studio_packages, 'verify', lambda *args: None)
    monkeypatch.setattr(joint_studio_paths, 'identities', lambda ctx: None)
    monkeypatch.setattr(joint_studio_paths, 'provision', lambda u: None)
    monkeypatch.setattr(operations, 'keep_assets', lambda *args: None)
    class Gateway:
        def preflight(self, before):
            state['gateway_events'].append('preflight')
        def ensure_private(self):
            state['accepting'] = False
            state['gateway_events'].append('private')
        def normalize(self, after, before):
            return after
        def open_public(self, expected):
            assert expected == state['after'] and w.tool.load()['current'] == expected
            assert not w.tool.load()['migration_pending']
            state['gateway_events'].append('open-after-ledger')
            state['accepting'] = True
        def seal(self):
            state['gateway_events'].append('sealed')
            state['accepting'] = False
    gateway = Gateway()
    monkeypatch.setattr(joint_studio_engine, 'context',
                        lambda *args, **kwargs: nullcontext(gateway if kwargs.get('private_gateway', True) else None))
    monkeypatch.setattr(joint_studio_release.fence, 'hold', lambda *args, **kwargs: nullcontext(99))
    monkeypatch.setattr(joint_studio_engine, 'check_migration', lambda *args: None)
    def prepare():
        (w.u.WORK / 'prepared.json').write_text('{}')
    def apply():
        (w.u.WORK / 'started.json').write_text('{}')
        if state['fail_apply'] == 'before':
            raise RuntimeError('before migration')
        state['schema']['domestic'] = '0043'
        if state['fail_apply'] == 'after':
            raise RuntimeError('after migration')
        state['runtime'] = copy.deepcopy(state['after'])
        (w.u.WORK / 'applied.json').write_text('{}')
    def recover():
        state['actions'].append('old-recovery')
        state['runtime'] = copy.deepcopy(current['current'])
        (w.u.WORK / 'rolled-back.json').write_text('{}')
    def resume(_):
        state['actions'].append('forward-recovery')
        state['runtime'] = copy.deepcopy(state['after'])
        (w.u.WORK / 'applied.json').write_text('{}')
    monkeypatch.setattr(engine, 'prepare', prepare)
    monkeypatch.setattr(engine, 'apply', apply)
    monkeypatch.setattr(engine, 'recover', recover)
    monkeypatch.setattr(engine, '_read', lambda name: {})
    monkeypatch.setattr(joint_studio_forward, 'resume', resume)
    return joint_studio_release.Upgrade(w.store), roots, state, current


def test_success_advances_all_scopes_and_keeps_migration_history(upgrade):
    tool, roots, state, old = upgrade
    assert tool.prepare(roots)['phase'] == 'prepared'
    assert tool.deploy()['phase'] == 'complete'
    data = tool.tool.load()
    assert data['current'] == state['after'] and not data['migration_pending']
    assert all(row['previous'] is None for row in data['groups'].values())
    assert set(data['migration_pins']) >= {old['current']['groups'][s]['frontend'] for s in scopes.GROUPS}
    assert state['gateway_events'] == ['preflight', 'private', 'open-after-ledger'] and state['accepting']
    assert tool.finish()['phase'] == 'complete'


def test_verification_failure_keeps_ingress_closed_and_retry_recovers(upgrade, monkeypatch):
    tool, roots, state, _ = upgrade
    tool.prepare(roots)
    capture = scope_snapshot.capture
    monkeypatch.setattr(scope_snapshot, 'capture',
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('runtime verification failed')))
    with pytest.raises(RuntimeError, match='runtime verification failed'):
        tool.deploy()
    assert not state['accepting'] and state['gateway_events'] == ['preflight', 'private', 'sealed']
    assert tool.read()['phase'] == 'forward-required' and tool.tool.load()['migration_pending']
    monkeypatch.setattr(scope_snapshot, 'capture', capture)
    assert tool.recover()['phase'] == 'complete'
    assert state['accepting'] and state['gateway_events'][-2:] == ['private', 'open-after-ledger']


def test_failure_after_ledger_recloses_and_recovers_forward(upgrade, monkeypatch):
    tool, roots, state, _ = upgrade
    tool.prepare(roots)
    manager = joint_studio_engine.context
    gateway = manager(None).__enter__()
    original = gateway.open_public
    def fail_after_open(expected):
        original(expected)
        raise RuntimeError('public health failed')
    monkeypatch.setattr(gateway, 'open_public', fail_after_open)
    with pytest.raises(RuntimeError, match='public health failed'):
        tool.deploy()
    assert not state['accepting'] and not tool.tool.load()['migration_pending']
    assert tool.read()['phase'] == 'forward-required'
    monkeypatch.setattr(gateway, 'open_public', original)
    assert tool.recover()['phase'] == 'complete' and state['accepting']


@pytest.mark.parametrize('persist_first', [False, True])
def test_terminal_marker_write_uncertainty_keeps_verified_runtime_recoverable(upgrade, monkeypatch, persist_first):
    tool, roots, state, _ = upgrade
    tool.prepare(roots)
    original = tool.save
    def interrupted(row, phase):
        if phase == 'complete':
            if persist_first:
                original(row, phase)
            raise RuntimeError('terminal marker write uncertain')
        original(row, phase)
    monkeypatch.setattr(tool, 'save', interrupted)
    with pytest.raises(RuntimeError, match='terminal marker write uncertain'):
        tool.deploy()
    assert state['accepting'] and not tool.tool.load()['migration_pending']
    assert tool.read()['phase'] in ('complete', 'forward-required')
    monkeypatch.setattr(tool, 'save', original)
    assert tool.recover()['phase'] == 'complete' and state['accepting']


@pytest.mark.parametrize('when', ['before', 'after'])
def test_failure_uses_only_schema_compatible_recovery(upgrade, when):
    tool, roots, state, old = upgrade
    tool.prepare(roots)
    state['fail_apply'] = when
    with pytest.raises(RuntimeError, match='migration'):
        tool.deploy()
    assert tool.read()['phase'] == ('interrupted' if when == 'before' else 'forward-required')
    result = tool.recover()
    assert result['phase'] == ('rolled-back' if when == 'before' else 'complete')
    assert state['actions'] == (['old-recovery'] if when == 'before' else ['forward-recovery'])
    assert tool.tool.load()['current'] == (old['current'] if when == 'before' else state['after'])


def test_interruption_before_ledger_flag_can_be_cancelled(upgrade, monkeypatch):
    tool, roots, state, old = upgrade
    original = tool.tool.save
    monkeypatch.setattr(tool.tool, 'save', lambda value: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError, match='interrupted'):
        tool.prepare(roots)
    monkeypatch.setattr(tool.tool, 'save', original)
    assert tool.recover()['phase'] == 'cancelled'
    assert tool.tool.load() == old


def test_private_preflight_failure_can_be_cancelled_before_migration(upgrade, monkeypatch):
    tool, roots, state, old = upgrade
    gateway = joint_studio_engine.context(None).__enter__()
    monkeypatch.setattr(gateway, 'preflight',
                        lambda before: (_ for _ in ()).throw(RuntimeError('private preflight failed')))
    with pytest.raises(RuntimeError, match='private preflight failed'):
        tool.prepare(roots)
    assert not state['accepting'] and state['schema']['domestic'] == '0032'
    assert tool.recover()['phase'] == 'cancelled'
    assert tool.tool.load() == old


def test_recovery_finishes_when_old_ledger_was_saved_before_marker(upgrade, monkeypatch):
    tool, roots, state, old = upgrade
    tool.prepare(roots)
    state['fail_apply'] = 'before'
    with pytest.raises(RuntimeError, match='before migration'):
        tool.deploy()
    original = tool.save
    def interrupted(row, phase):
        if phase == 'rolled-back':
            raise SystemExit('injected interruption')
        original(row, phase)
    monkeypatch.setattr(tool, 'save', interrupted)
    with pytest.raises(SystemExit, match='injected'):
        tool.recover()
    assert tool.tool.load() == old and tool.read()['phase'] == 'interrupted'
    monkeypatch.setattr(tool, 'save', original)
    assert tool.recover()['phase'] == 'rolled-back'
    joint_studio_marker.guard(tool.u, tool.store)
    assert state['actions'] == ['old-recovery']


def test_crash_during_success_ledger_write_can_finish_forward(upgrade, monkeypatch):
    tool, roots, state, _ = upgrade
    tool.prepare(roots)
    original = tool.tool.save
    def fail_completed(value):
        if value['current'] == state['after']:
            raise RuntimeError('ledger write interrupted')
        original(value)
    monkeypatch.setattr(tool.tool, 'save', fail_completed)
    with pytest.raises(RuntimeError, match='ledger write'):
        tool.deploy()
    assert tool.read()['phase'] == 'ledger-writing'
    monkeypatch.setattr(tool.tool, 'save', original)
    assert tool.recover()['phase'] == 'complete'
    assert state['actions'] == ['forward-recovery']


def test_pending_marker_blocks_other_release_paths(upgrade):
    tool, roots, _, _ = upgrade
    tool.prepare(roots)
    with pytest.raises(RuntimeError, match='pending domestic Studio'):
        joint_studio_marker.guard(tool.u, tool.store)


@pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0,
                    reason='requires isolated root Linux process locks')
def test_real_recovery_waits_for_migration_child_after_parent_death(upgrade, tmp_path, monkeypatch):
    tool, roots, state, _ = upgrade
    row = tool.prepare(roots)
    tool.save(row, 'interrupted')
    work = Path(row['work'])
    (work / 'started.json').write_text('{}')
    (work / 'domestic-migration.json').write_text('{}')
    monkeypatch.setattr(joint_studio_release.fence, 'hold', REAL_FENCE_HOLD)
    monkeypatch.setattr(joint_studio_release.fence, 'wait_database',
                        lambda u, ctx: state['actions'].append('database-barrier'))
    monkeypatch.setattr(engine, '_load_state', lambda baseline: {'ctx': {'hengxin-vps-codex-worker': {}}})
    ready, proceed = tmp_path / 'child-ready', tmp_path / 'child-proceed'
    code = ("import pathlib,sys,time\nready,proceed=map(pathlib.Path,sys.argv[1:])\n"
            "ready.write_text('ready')\nwhile not proceed.exists(): time.sleep(.02)\n")
    parent = ("import subprocess,sys\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
              "sys.path.insert(0,sys.argv[1])\nimport joint_studio_fence as f\n"
              "u=SimpleNamespace(WORK=Path(sys.argv[2]),safe=lambda path:None)\n"
              "with f.hold(u) as fd:\n"
              " p=subprocess.Popen([sys.executable,'-c',sys.argv[3],*sys.argv[4:]],pass_fds=(fd,),"
              "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n p.wait()\n")
    process = subprocess.Popen([sys.executable, '-c', parent, str(Path(__file__).parent), str(work), code,
                                str(ready), str(proceed)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists()
        process.kill()
        process.wait(timeout=5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            recovery = pool.submit(tool.recover)
            time.sleep(.3)
            assert not recovery.done() and not state['actions']
            state['schema']['domestic'] = '0043'
            proceed.write_text('finish')
            assert recovery.result(timeout=10)['phase'] == 'complete'
        assert state['actions'] == ['database-barrier', 'forward-recovery']
    finally:
        proceed.touch()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.skipif(not os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL') or sys.platform != 'linux',
                    reason='requires the disposable local PostgreSQL test database')
def test_real_recovery_waits_for_prior_database_transaction(upgrade, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    url = make_url(os.environ['TEST_DOMESTIC_STUDIO_DATABASE_URL'])
    if url.host not in ('127.0.0.1', 'localhost') or not (url.database or '').endswith('_test'):
        pytest.fail('Only a disposable local *_test database is allowed')
    module_path = (Path(__file__).resolve().parents[3] /
                   'hengxin-smart-image/backend/app/modules/domestic_studio/migration_barrier.py')
    spec = importlib.util.spec_from_file_location('migration_barrier_integration_test', module_path)
    barrier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(barrier)
    tool, roots, state, _ = upgrade
    row = tool.prepare(roots)
    tool.save(row, 'interrupted')
    work = Path(row['work'])
    (work / 'started.json').write_text('{}')
    (work / 'domestic-migration.json').write_text('{}')
    monkeypatch.setattr(joint_studio_release.fence, 'hold', REAL_FENCE_HOLD)
    monkeypatch.setattr(engine, '_load_state', lambda baseline: {'ctx': {'hengxin-vps-codex-worker': {}}})
    db = create_engine(url)
    def wait_database(u, ctx):
        with db.begin() as connection:
            barrier.acquire(connection)
        state['actions'].append('database-barrier')
    monkeypatch.setattr(joint_studio_release.fence, 'wait_database', wait_database)
    try:
        with db.connect() as first, ThreadPoolExecutor(max_workers=1) as pool:
            transaction = first.begin()
            barrier.acquire(first)
            recovery = pool.submit(tool.recover)
            time.sleep(.3)
            assert not recovery.done() and not state['actions']
            state['schema']['domestic'] = '0043'
            transaction.commit()
            assert recovery.result(timeout=10)['phase'] == 'complete'
        assert state['actions'] == ['database-barrier', 'forward-recovery']
    finally:
        db.dispose()
