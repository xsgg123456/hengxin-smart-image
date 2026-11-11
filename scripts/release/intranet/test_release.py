import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import release as cli
import operations
import snapshot


@pytest.fixture
def tool(tmp_path, monkeypatch):
    store = cli.retention_store(tmp_path)
    tool = cli.Release(store)
    monkeypatch.setattr(tool.u, 'safe', lambda *a, **k: None)
    before = {'backend': '/opt/hengxin-unified-releases/old',
              'frontend': '/opt/hengxin-unified-releases/old',
              'backend_commit': 'a'*40, 'frontend_commit': 'a'*40,
              'native': {}, 'images': {}, 'data': {}, 'schema': {}, 'binaries': {}}
    tool.save(dict(version=1, current=before, previous=None, last=None, pending=None))
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: before.copy())
    monkeypatch.setattr(snapshot, 'schemas', lambda *a: {})
    monkeypatch.setattr(tool.u, 'data_identity', lambda: {})
    # Existing state-machine tests stub the external full-fleet catalog boundary.
    # test_catalog exercises its real A/B/C advancement and retention behavior.
    monkeypatch.setattr(cli.catalog, 'before', lambda u, store, data: data)
    monkeypatch.setattr(cli.catalog, 'advance', lambda u, store, old, new, item: new)
    return tool, before


def pending(tool, before, phase='prepared', mode='full'):
    work = tool.store.root / 'intranet-transactions' / 'test'
    work.mkdir(parents=True)
    item = {'release': '/opt/hengxin-unified-releases/new', 'work': str(work),
            'mode': mode, 'phase': phase, 'before': before}
    data = tool.load()
    data['pending'] = item
    tool.save(data)
    return item


def test_initialize_rechecks_existing_baseline(tool, monkeypatch):
    subject, before = tool
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: dict(before, backend='changed'))
    with pytest.raises(RuntimeError, match='drift'):
        subject.init()


def test_shared_lock_rejects_parallel_release(tmp_path):
    first, second = cli.retention_store(tmp_path), cli.retention_store(tmp_path)
    with first.locked():
        with pytest.raises(OSError):
            with second.locked():
                pytest.fail('concurrent release acquired lock')


@pytest.mark.parametrize('name', ['/tmp/x', '/opt/hengxin-unified-releases/a/../b', '/opt/hengxin-unified-releases/.secret'])
def test_release_root_is_fixed(name):
    with pytest.raises(RuntimeError):
        snapshot.release_path(name)


@pytest.mark.parametrize('path', ['backend/uv.lock', 'backend/pyproject.toml', 'backend/migrations/a.py'])
def test_dependency_or_schema_change_blocks(path):
    with pytest.raises(RuntimeError, match='upgrade'):
        snapshot.compatible({'files': {path: 'old'}}, {'files': {path: 'new'}}, 'full')


def test_frontend_mode_rejects_changed_backend():
    with pytest.raises(RuntimeError, match='backend'):
        snapshot.compatible({'files': {'backend/app/main.py': 'a'}},
                            {'files': {'backend/app/main.py': 'b'}}, 'frontend')


def test_frontend_requirements_chunk_is_not_a_dependency_input():
    snapshot.compatible({'files': {'frontend/assets/requirements-old.js': 'a'}},
                        {'files': {'frontend/assets/requirements-new.js': 'b'}}, 'frontend')


def test_frontend_checks_actual_lan_binding_and_served_bytes(monkeypatch):
    def open_bound_port(url, timeout):
        if url != 'http://192.168.1.245:8080/':
            raise ConnectionRefusedError('web does not bind loopback')
        return io.BytesIO(b'live-index')
    monkeypatch.setattr(snapshot.urllib.request, 'urlopen', open_bound_port)
    snapshot.verify_frontend({'files': {'frontend/index.html': snapshot.sha(b'live-index')}})
    with pytest.raises(RuntimeError, match='Served frontend differs'):
        snapshot.verify_frontend({'files': {'frontend/index.html': snapshot.sha(b'stale-index')}})


def test_schema_uses_each_business_migration_table(monkeypatch):
    monkeypatch.setattr(snapshot, 'database', lambda u, side: (side, 'user', 'database'))
    queries = []
    def run(args):
        queries.append((args[2], args[-1]))
        return 'domestic_revision' if args[2] == 'domestic' else 'overseas_revision'
    result = snapshot.schemas(SimpleNamespace(run=run))
    assert queries == [('domestic', 'SELECT version_num FROM alembic_version ORDER BY version_num'),
                       ('overseas', 'SELECT version_num FROM overseas_alembic_version ORDER BY version_num')]
    assert result == {'domestic': 'domestic_revision', 'overseas': 'overseas_revision'}


def test_deploy_verifies_before_advancing(tool, monkeypatch):
    subject, before = tool
    item = pending(subject, before)
    after = dict(before, backend=item['release'], frontend=item['release'])
    state = {'live': before}
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: state['live'].copy())
    monkeypatch.setattr(operations, 'backup', lambda *a: None)
    monkeypatch.setattr(cli.engine, 'apply', lambda: state.update(live=after))
    calls = []
    def cleanup(data, automatic=False):
        assert subject.load()['current'] == after and subject.load()['pending'] is None
        assert automatic
        calls.append('cleaned')
    monkeypatch.setattr(subject, 'cleanup', cleanup)
    result = subject.deploy()
    assert result['current'] == after and result['previous'] == before and result['pending'] is None
    assert calls == ['cleaned']


def test_postcheck_failure_restores_and_keeps_recovery_receipt(tool, monkeypatch):
    subject, before = tool
    pending(subject, before)
    calls = []
    monkeypatch.setattr(operations, 'backup', lambda *a: None)
    monkeypatch.setattr(cli.engine, 'apply', lambda: None)
    monkeypatch.setattr(subject, 'restore', lambda item: calls.append('restored'))
    monkeypatch.setattr(subject, 'cleanup', lambda *a, **k: pytest.fail('failed release must not clean'))
    with pytest.raises(RuntimeError, match='did not switch'):
        subject.deploy()
    assert calls == ['restored']
    assert subject.load()['pending']['phase'] == 'recovered'
    assert subject.load()['current'] == before


def test_interrupted_deploy_cannot_restart(tool):
    subject, before = tool
    pending(subject, before, phase='deploying')
    with pytest.raises(RuntimeError, match='recover'):
        subject.deploy()


def test_started_release_cannot_cancel(tool):
    subject, before = tool
    item = pending(subject, before)
    (Path(item['work']) / 'started.json').write_text('{}')
    with pytest.raises(RuntimeError, match='cannot be abandoned'):
        subject.cancel()


def test_unstarted_candidate_can_cancel_without_business_mutation(tool):
    subject, before = tool
    pending(subject, before)
    assert subject.cancel()['pending'] is None
    assert subject.load()['current'] == before


def test_schema_drift_blocks_recovery_before_any_switch(tool, monkeypatch):
    subject, before = tool
    item = pending(subject, before, phase='deploying')
    monkeypatch.setattr(snapshot, 'schemas', lambda *a: {'domestic': 'new'})
    monkeypatch.setattr(cli.engine, 'recover', lambda: pytest.fail('must not switch'))
    with pytest.raises(RuntimeError, match='Schema/data drift'):
        subject.restore(item)


def test_rollback_keeps_pending_until_restore_verified(tool, monkeypatch):
    subject, before = tool
    item = pending(subject, before)
    data = subject.load()
    data.update(pending=None, last=item, previous=before)
    subject.save(data)
    monkeypatch.setattr(subject, 'restore', lambda item: (_ for _ in ()).throw(RuntimeError('failed')))
    with pytest.raises(RuntimeError):
        subject.rollback()
    assert subject.load()['pending']['phase'] == 'rollback'


def test_production_host_is_checked_before_opening_store(monkeypatch):
    monkeypatch.setattr(cli.socket, 'gethostname', lambda: 'old-public')
    monkeypatch.setattr(cli, 'retention_store', lambda *a: pytest.fail('must not write'))
    with pytest.raises(RuntimeError, match='hengxin-ai-245'):
        cli.main(['init'])


def test_assets_preserve_old_hashes_but_not_old_index(tmp_path, monkeypatch):
    old, new = tmp_path/'old', tmp_path/'new'
    for root in (old, new):
        (root/'frontend/assets').mkdir(parents=True)
        (root/'frontend/index.html').write_text(root.name)
    (old/'frontend/assets/old-hash.js').write_text('old')
    (old/'release-manifest.json').write_text(json.dumps({'files': {'frontend/assets/old-hash.js': snapshot.sha(b'old')}}))
    (new/'release-manifest.json').write_text(json.dumps({'files': {'frontend/index.html': 'new'}}))
    u = SimpleNamespace(safe=lambda *a, **k: None,
                        write=lambda path, data, **k: path.write_bytes(data))
    operations.keep_assets(u, old, new)
    assert (new/'frontend/index.html').read_text() == 'new'
    assert (new/'frontend/assets/old-hash.js').read_text() == 'old'
    assert 'frontend/assets/old-hash.js' in json.loads((new/'release-manifest.json').read_text())['compatibility_files']


def test_assets_do_not_accumulate_across_three_successes(tmp_path):
    u = SimpleNamespace(safe=lambda *a, **k: None,
                        write=lambda path, data, **k: path.write_bytes(data))
    roots = [tmp_path/name for name in ('A', 'B', 'C')]
    for root in roots:
        (root/'frontend/assets').mkdir(parents=True)
        name = 'frontend/assets/' + root.name + '.js'
        (root/name).write_bytes(root.name.encode())
        files = {name: snapshot.sha(root.name.encode())}
        (root/'release-manifest.json').write_text(json.dumps({'files': files, 'frontend_current_files': files}))
    operations.keep_assets(u, roots[0], roots[1])
    operations.keep_assets(u, roots[1], roots[2])
    assert sorted(p.name for p in (roots[2]/'frontend/assets').iterdir()) == ['B.js', 'C.js']
    manifest = json.loads((roots[2]/'release-manifest.json').read_bytes())
    assert set(manifest['compatibility_files']) == {'frontend/assets/B.js'}
    assert set(manifest['frontend_current_files']) == {'frontend/assets/C.js'}


def test_web_recovery_refuses_concurrent_compose(tmp_path):
    compose = tmp_path/'compose.json'
    compose.write_bytes(b'foreign')
    (tmp_path/'web-before.json').write_bytes(b'old')
    (tmp_path/'compose.candidate.json').write_bytes(b'new')
    (tmp_path/'web-prepared.json').write_text(json.dumps({'before': snapshot.sha(b'old'), 'candidate': snapshot.sha(b'new')}))
    u = SimpleNamespace(WORK=tmp_path, COMPOSE=compose, safe=lambda *a: None)
    with pytest.raises(RuntimeError, match='Concurrent'):
        operations.recover_web(u)
    assert compose.read_bytes() == b'foreign'


@pytest.mark.parametrize('mode', ['full', 'frontend'])
def test_cleanup_failure_does_not_rollback_success(tool, monkeypatch, mode, capsys):
    subject, before = tool
    item = pending(subject, before, mode=mode)
    after = dict(before, frontend=item['release'],
                 backend=item['release'] if mode == 'full' else before['backend'])
    state = {'live': before}
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: state['live'].copy())
    monkeypatch.setattr(operations, 'backup', lambda *a: None)
    monkeypatch.setattr(cli.engine, 'apply', lambda: state.update(live=after))
    monkeypatch.setattr(operations, 'apply_web', lambda *a: state.update(live=after))
    monkeypatch.setattr(subject, 'restore', lambda *a: pytest.fail('must not roll back'))
    monkeypatch.setattr(cli.cleanup, 'execute', lambda *a, **k: (_ for _ in ()).throw(OSError('disk error')))
    assert subject.deploy()['current'] == after
    assert subject.load()['pending'] is None
    assert 'warning' in capsys.readouterr().out


def test_cleanup_defaults_to_preview_and_uses_release_lock(tool, monkeypatch):
    subject, _ = tool
    monkeypatch.setattr(cli.socket, 'gethostname', lambda: 'hengxin-ai-245')
    monkeypatch.setattr(cli.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(cli, 'retention_store', lambda *a: subject.store)
    calls = []
    def execute(u, store, data, apply=False):
        with pytest.raises(OSError):
            with cli.retention_store().locked():
                pytest.fail('cleanup did not acquire release lock')
        calls.append(apply)
        return {'status': 'preview'}
    monkeypatch.setattr(cli.cleanup, 'execute', execute)
    cli.main(['cleanup'])
    cli.main(['cleanup', '--apply'])
    assert calls == [False, True]
