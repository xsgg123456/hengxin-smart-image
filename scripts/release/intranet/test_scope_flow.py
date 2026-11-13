"""Offline Release integration: real scope composition, ledger and retention clock."""
import copy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import catalog
import image_gc
import release
import scope_catalog
import scope_changes
import scope_snapshot
import scopes
import snapshot


@pytest.fixture
def world(tmp_path, monkeypatch):
    roots = tmp_path / 'releases'
    roots.mkdir()
    monkeypatch.setattr(snapshot, 'RELEASES', roots)
    store = release.retention_store(tmp_path / 'ledger')
    tool = release.Release(store)
    # Preserve the production ownership inventory, never a fictitious two-service map.
    real = release.engine.u
    u = SimpleNamespace(APPS=real.APPS, DATA=real.DATA, NATIVE=real.NATIVE.copy(),
                        PYTHON_SERVICES=real.PYTHON_SERVICES.copy(), WORKERS=real.WORKERS,
                        ENTRIES=real.ENTRIES, ROOT=tmp_path, COMPOSE=tmp_path / 'compose.json',
                        RELEASE=roots / 'initial', WORK=tmp_path / 'unused', REUSABLE=True,
                        SYSTEMD=tmp_path / 'systemd', DROPIN=real.DROPIN,
                        candidate_compose=None, digest=snapshot.sha)
    u.safe = lambda *a, **k: None
    u.write = lambda p, b, **k: Path(p).write_bytes(b)
    for name in ('contexts', 'drain', 'gate_accounts', 'stop_apps', 'start_apps', 'health',
                 'probe_candidate', 'app_command', 'remove_stop_overrides'):
        setattr(u, name, lambda *a, **k: None)
    u.validate_release = lambda: snapshot.sha((u.RELEASE / 'release-manifest.json').read_bytes())
    tool.u = u
    monkeypatch.setattr(release.engine, 'u', u)
    w = SimpleNamespace(tool=tool, u=u, roots=roots, store=store, failure=None,
                        cleanups=[], backups=[], transitions=[])

    def make(name, scope, backend=None):
        root = roots / name
        (root / 'frontend/assets').mkdir(parents=True)
        (root / 'backend/app').mkdir(parents=True)
        files = {'backend/' + module.replace('.', '/') + '.py': b'VALUE = 1\n'
                 for entries in scope_changes.ENTRYPOINTS.values() for module in entries}
        files.update(backend or {})
        files.update({'frontend/index.html': name.encode(),
                      'frontend/assets/' + name + '.js': name.encode()})
        for filename, content in files.items():
            (root / filename).parent.mkdir(parents=True, exist_ok=True)
            (root / filename).write_bytes(content)
        hashes = {n: snapshot.sha(b) for n, b in files.items()}
        manifest = {'commit': snapshot.sha(name.encode())[:40], 'scope': scope,
                    'files': hashes, 'provenance': {'source_files': hashes.copy()}}
        (root / 'release-manifest.json').write_text(json.dumps(manifest))
        return root
    w.make = make
    initial = {s: make(s + '-initial', s) for s in scopes.GROUPS}
    services = {n: {'image': 'unchanged', 'volumes': []}
                for n in (*u.APPS, *u.DATA, *scopes.UI.values())}
    for s in scopes.GROUPS:
        for n in scopes.APPS[s]:
            services[n]['volumes'] = [{'type': 'bind', 'source': str(initial[s] / 'backend/app'),
                                      'target': '/app/app', 'read_only': True}]
        services[scopes.UI[s]]['volumes'] = [{'type': 'bind', 'source': str(initial[s] / 'frontend'),
                                             'target': '/usr/share/nginx/html', 'read_only': True}]
    u.COMPOSE.write_text(json.dumps({'name': 'hengxin-lan', 'services': services}))
    names = set(services) | {'https'}
    w.inventory = {n: {'Id': 'id-' + n, 'Name': '/hengxin-lan-' + n,
                         'Image': 'sha256:' + snapshot.sha(n.encode()),
                         'Config': {'Labels': {'com.docker.compose.service': n,
                                    'com.docker.compose.project': 'hengxin-lan-edge' if n == 'https' else 'hengxin-lan'}},
                         'State': {'Running': True, 'StartedAt': 'original-start'}} for n in names}
    w.native = {n: {'MainPID': str(i + 10), 'ExecMainStartTimestampMonotonic': '100'}
                for i, n in enumerate(u.NATIVE)}
    u.prop = lambda n, k: w.native[n][k]
    def run(argv, **kwargs):
        if argv == ['docker', 'ps', '-aq', '--no-trunc']:
            return ' '.join(v['Id'] for v in w.inventory.values())
        if argv[:2] == ['docker', 'inspect']:
            return json.dumps(list(w.inventory.values()))
        pytest.fail('Unexpected external command: ' + repr(argv))
    u.run = run
    schema = {'domestic': 'schema-domestic', 'overseas': 'schema-overseas'}
    u.data_identity = lambda: {'postgres': 'original-volume'}
    monkeypatch.setattr(snapshot, 'schemas', lambda u: schema.copy())
    def capture(u, runtime=False):
        config = json.loads(u.COMPOSE.read_bytes())
        groups = {}
        for s in scopes.GROUPS:
            def mount(n, target):
                return Path(next(v['source'] for v in config['services'][n]['volumes'] if v['target'] == target))
            backend = mount(scopes.APPS[s][0], '/app/app').parent.parent
            frontend = mount(scopes.UI[s], '/usr/share/nginx/html').parent
            bm, fm = snapshot.manifest(u, backend), snapshot.manifest(u, frontend)
            groups[s] = dict(backend=str(backend), frontend=str(frontend),
                             backend_commit=bm['commit'], frontend_commit=fm['commit'],
                             backend_manifest=snapshot.sha((backend / 'release-manifest.json').read_bytes()),
                             frontend_manifest=snapshot.sha((frontend / 'release-manifest.json').read_bytes()))
        return dict(groups=groups, images=image_gc.capture(image_gc.scoped(u)),
                    native={n: {'python': 'unchanged'} for n in w.native}, binaries={},
                    data=u.data_identity(), schema=schema.copy(), configs={})
    monkeypatch.setattr(scope_snapshot, 'capture', capture)
    # Only engine's host mutations are simulated; scope context/composition is real.
    def prepare():
        u.WORK.mkdir()
        old = u.COMPOSE.read_bytes()
        (u.WORK / 'before.json').write_bytes(old)
        candidate = u.candidate_compose(json.loads(old))
        (u.WORK / 'compose.candidate.json').write_text(json.dumps(candidate))
        (u.WORK / 'prepared.json').write_text(json.dumps({'configs': [], 'dropins': {}}))
    def apply():
        (u.WORK / 'started.json').write_text('{}')
        w.transitions.append((tuple(u.APPS), tuple(u.NATIVE)))
        if w.failure == 'drain':
            raise RuntimeError('drain deadline exceeded')
        if w.failure != 'no-switch':
            u.COMPOSE.write_bytes((u.WORK / 'compose.candidate.json').read_bytes())
        if w.failure == 'other-restart':
            w.inventory['overseas-api']['State']['StartedAt'] = 'unexpected-start'
        (u.WORK / 'applied.json').write_text('{}')
    def recover():
        u.COMPOSE.write_bytes((u.WORK / 'before.json').read_bytes())
        (u.WORK / 'rolled-back.json').write_text('{}')
    monkeypatch.setattr(release.engine, 'prepare', prepare)
    monkeypatch.setattr(release.engine, 'apply', apply)
    monkeypatch.setattr(release.engine, 'recover', recover)
    monkeypatch.setattr(release.operations, 'backup', lambda u, work, scope=None: w.backups.append(scope))
    monkeypatch.setattr(tool, 'cleanup', lambda data, automatic=False: w.cleanups.append(copy.deepcopy(data)))
    if os.name == 'nt':
        # POSIX descriptor/inode proofs are separately exercised on Linux below.
        monkeypatch.setattr(catalog.artifact_gc, 'proof', lambda u, s, p, k: {
            'path': str(p), 'kind': k, 'files': {str(f.relative_to(p)): snapshot.sha(f.read_bytes())
                for f in Path(p).rglob('*') if f.is_file()}})
    current = capture(u)
    data = dict(version=2, current=current, previous=None, pending=None, last=None,
                groups={s: dict(current=scope_snapshot.group(current, s), previous=None,
                                current_work=None, previous_work=None, last=None) for s in scopes.GROUPS},
                retention=dict(version=2, known_images=sorted(set(current['images'].values())),
                               artifacts={}, staged={}, unowned=[]), source_history=[])
    scope_catalog.seal(data)
    tool.save(data)
    return w


def publish(w, name, scope='domestic', mode='frontend', backend=None):
    root = w.make(name, scope, backend)
    w.tool.prepare(root, mode, scope)
    return w.tool.deploy()


@pytest.mark.parametrize('mode', ['frontend', 'full'])
def test_interleaved_success_and_rollback_keep_other_group_and_shared_backend(world, mode):
    w = world
    baseline = w.tool.load()
    a = publish(w, 'A', mode=mode)
    b = publish(w, 'B', mode=mode)
    x = publish(w, 'X', 'overseas', mode)
    c = publish(w, 'C', mode=mode)
    assert c['groups']['overseas'] == x['groups']['overseas']
    assert c['groups']['shared'] == baseline['groups']['shared']
    assert c['groups']['domestic']['previous'] == b['groups']['domestic']['current']
    assert c['groups']['domestic']['current']['images'] == a['groups']['domestic']['current']['images']
    result = w.tool.rollback('domestic')
    assert result['groups']['domestic']['current'] == b['groups']['domestic']['current']
    assert result['groups']['domestic']['previous'] == c['groups']['domestic']['current']
    assert result['groups']['overseas'] == x['groups']['overseas']
    assert result['groups']['shared'] == baseline['groups']['shared']
    assert scope_snapshot.capture(w.u) == result['current']
    catalog.check(result)
    assert len(w.cleanups) == 5
    assert all(not data['pending'] for data in w.cleanups)
    selected = ['domestic', 'domestic', 'overseas', 'domestic', 'domestic']
    assert w.backups == (selected if mode == 'full' else [])
    assert w.transitions == [(tuple((*scopes.APPS[s], scopes.UI[s])) if mode == 'full' else (scopes.UI[s],),
                              tuple(scopes.NATIVE[s]) if mode == 'full' else ()) for s in selected]


def test_interleaved_real_backend_changes_and_independent_rollback(world):
    w = world
    domestic, overseas = 'backend/app/main.py', 'backend/app/overseas/main.py'
    baseline = w.tool.load()
    a = publish(w, 'A', mode='full', backend={domestic: b'VALUE = 2\n'})
    x = publish(w, 'X', 'overseas', 'full',
                backend={domestic: b'VALUE = 2\n', overseas: b'VALUE = 2\n'})
    c = publish(w, 'C', mode='full',
                backend={domestic: b'VALUE = 3\n', overseas: b'VALUE = 2\n'})
    assert x['groups']['domestic'] == a['groups']['domestic']
    assert c['groups']['overseas'] == x['groups']['overseas']
    assert c['groups']['domestic']['previous'] == a['groups']['domestic']['current']
    result = w.tool.rollback('domestic')
    assert result['groups']['domestic']['current'] == a['groups']['domestic']['current']
    assert result['groups']['domestic']['previous'] == c['groups']['domestic']['current']
    assert result['groups']['overseas'] == x['groups']['overseas']
    assert result['groups']['shared'] == baseline['groups']['shared']
    assert (Path(result['groups']['domestic']['current']['backend']) / domestic).read_bytes() == b'VALUE = 2\n'
    assert (Path(result['groups']['overseas']['current']['backend']) / overseas).read_bytes() == b'VALUE = 2\n'
    assert scope_snapshot.capture(w.u) == result['current']
    catalog.check(result)
    assert w.backups == ['domestic', 'overseas', 'domestic', 'domestic']
    assert len(w.cleanups) == 4


@pytest.mark.parametrize('target,other', [('domestic', 'overseas'), ('overseas', 'domestic')])
def test_frontend_after_other_backend_advance_keeps_both_backends(world, target, other):
    w = world
    other_entry = 'backend/' + scope_changes.ENTRYPOINTS[other][0].replace('.', '/') + '.py'
    source = {other_entry: b'VALUE = 2\n'}
    advanced = publish(w, 'other-backend', other, 'full', backend=source)
    result = publish(w, 'target-frontend', target, 'frontend', backend=source)
    assert result['groups'][other] == advanced['groups'][other]
    assert result['groups']['shared'] == advanced['groups']['shared']
    assert result['groups'][target]['current']['backend'] == advanced['groups'][target]['current']['backend']
    assert result['groups'][target]['current']['frontend'] == str(w.roots / 'target-frontend')
    assert scope_snapshot.capture(w.u) == result['current']
    assert w.transitions[-1] == ((scopes.UI[target],), ())
    catalog.check(result)


@pytest.mark.parametrize('failure', ['drain', 'no-switch', 'other-restart'])
def test_failed_scope_release_never_advances_or_cleans(world, failure):
    w = world
    before = publish(w, 'A')
    w.failure = failure
    candidate = w.make('failed', 'domestic')
    w.tool.prepare(candidate, 'full', 'domestic')
    with pytest.raises(RuntimeError, match='drain|did not switch|Unrelated running service|Unaffected runtime'):
        w.tool.deploy()
    after = w.tool.load()
    assert after['groups'] == before['groups']
    assert after['retention'] == before['retention']
    assert after['current'] == before['current']
    assert after['pending']['phase'] == 'recovered'
    assert len(w.cleanups) == 1
    assert w.backups == ['domestic']
    catalog.check(after)


@pytest.mark.parametrize('change', ['current', 'history', 'digest'])
def test_sealed_catalog_refuses_live_and_history_drift(world, change):
    data = publish(world, 'A')
    if change == 'current':
        data['current']['groups']['overseas']['frontend'] += '-tampered'
    elif change == 'history':
        data['groups']['overseas']['previous_work'] = 'forged-work'
    else:
        data['retention']['groups']['domestic'] = 'forged-digest'
    with pytest.raises(RuntimeError, match='drift'):
        catalog.check(data)


def test_interrupted_deploy_requires_recover_and_does_not_advance(world):
    w = world
    before = publish(w, 'A')
    root = w.make('interrupted', 'domestic')
    prepared = w.tool.prepare(root, 'frontend', 'domestic')
    item = prepared['pending']
    item['phase'] = 'deploying'
    w.tool.save(prepared)
    (Path(item['work']) / 'started.json').write_text('{}')
    w.u.COMPOSE.write_bytes((Path(item['work']) / 'compose.candidate.json').read_bytes())
    with pytest.raises(RuntimeError, match='interrupted releases require recover'):
        w.tool.deploy()
    recovered = w.tool.recover()
    assert recovered['current'] == before['current']
    assert recovered['groups'] == before['groups']
    assert recovered['pending'] is None
    assert recovered['retention']['groups'] == before['retention']['groups']
    assert item['work'] in recovered['retention']['artifacts']
    assert len(w.cleanups) == 1


def test_cleanup_failure_does_not_undo_independent_success(world, monkeypatch, capsys):
    w = world
    monkeypatch.setattr(w.tool, 'cleanup', release.Release.cleanup.__get__(w.tool))
    monkeypatch.setattr(release.cleanup, 'execute', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
    data = publish(w, 'A')
    assert w.tool.load() == data
    assert data['groups']['domestic']['current']['frontend'] == str(w.roots / 'A')
    assert data['pending'] is None
    assert 'warning' in capsys.readouterr().out


def test_long_idle_side_previous_and_shared_sources_survive_many_domestic_releases(world):
    w = world
    overseas_before = w.tool.load()['groups']['overseas']['current']
    x = publish(w, 'X', 'overseas')
    for name in ('A', 'B', 'C', 'D'):
        data = publish(w, name)
    sources, paths = catalog.protected(data)
    assert {overseas_before['frontend'], x['groups']['overseas']['current']['frontend'],
            data['groups']['shared']['current']['backend'],
            data['groups']['domestic']['current']['backend']} <= sources
    assert data['groups']['overseas'] == x['groups']['overseas']
    assert str(w.roots / 'A') not in sources and str(w.roots / 'B') not in sources
    assert {str(w.roots / 'C'), str(w.roots / 'D')} <= sources
    assert x['last']['work'] in paths


@pytest.mark.skipif(os.name == 'nt', reason='Real POSIX descriptor deletion requires Linux')
def test_real_gc_preserves_idle_overseas_and_current_previous_transaction_files(world, monkeypatch):
    w = world
    monkeypatch.setattr(catalog.artifact_gc.cleanup_refs, 'host', lambda *a: {})
    x = publish(w, 'X', 'overseas')
    a, b, c = (publish(w, n) for n in ('A', 'B', 'C'))
    sources, paths = catalog.protected(c)
    result = catalog.artifact_gc.execute(w.u, w.store, c['retention']['artifacts'], sources, paths, apply=True)
    assert result['status'] == 'complete'
    assert result['deleted'] == [a['last']['work']]
    assert not Path(a['last']['work']).exists()
    for data in (x, b, c):
        assert (Path(data['last']['work']) / 'applied.json').exists()


@pytest.mark.skipif(os.name == 'nt', reason='Real source references and descriptor deletion require Linux')
def test_real_source_gc_retains_all_group_histories_dependencies_and_live_references(world, monkeypatch):
    import cleanup
    import cleanup_refs
    w = world
    x = publish(w, 'X', 'overseas')
    for name in ('obsolete', 'dependency', 'still-mounted', 'C', 'D'):
        data = publish(w, name)
    dependency = w.roots / 'dependency/backend/.venv'
    dependency.mkdir()
    (dependency / 'pyvenv.cfg').write_text('home = /usr/bin')
    # Preserve the real group ledger reference scan; simulate only host inspection.
    def scan_host(u, refs):
        refs.path(str(w.roots / 'still-mounted/backend/app'), 'container-mount')
        return {k: sorted(v) for k, v in refs.reasons.items()}
    monkeypatch.setattr(cleanup_refs, 'scan_host', scan_host)
    before = cleanup.tree_size(w.roots) + cleanup.tree_size(w.store.root)
    report = cleanup.execute(w.u, w.store, data, apply=True)
    after = cleanup.tree_size(w.roots) + cleanup.tree_size(w.store.root)
    assert report['status'] == 'complete'
    assert report['deleted'] == [str(w.roots / 'obsolete')]
    assert report['net_released_bytes'] == before - after
    assert dependency.exists()
    assert (w.roots / 'still-mounted').exists()
    assert (w.roots / 'C').exists() and (w.roots / 'D').exists()
    for scope, row in data['groups'].items():
        for key in ('current', 'previous'):
            if row[key]:
                assert Path(row[key]['backend']).exists()
                assert Path(row[key]['frontend']).exists()
    assert data['groups']['overseas'] == x['groups']['overseas']


def test_census_detects_other_side_restart_from_real_service_labels(world):
    before = scope_snapshot.census(world.u)
    world.inventory['overseas-api']['State']['StartedAt'] = 'restarted'
    after = scope_snapshot.census(world.u)
    import scope_release
    with pytest.raises(RuntimeError, match='Unrelated running service|Unaffected runtime'):
        scope_release.unaffected(before, after, 'domestic', 'full')


def test_rollback_keeps_outgoing_assets_without_editing_history_and_next_release_replaces_fallback(world):
    w = world
    publish(w, 'asset-A')
    b = publish(w, 'asset-B')
    b_root = Path(b['groups']['domestic']['current']['frontend'])
    before = {str(p.relative_to(b_root)): p.read_bytes() for p in b_root.rglob('*') if p.is_file()}
    c = publish(w, 'asset-C')
    c_root = Path(c['groups']['domestic']['current']['frontend'])
    overseas = c['groups']['overseas']
    w.tool.rollback('domestic')
    def mounts():
        config = json.loads(w.u.COMPOSE.read_bytes())
        return {v['target']: v for v in config['services']['domestic-ui']['volumes']}
    actual = mounts()
    assert actual['/usr/share/nginx/html']['source'] == str(b_root/'frontend')
    assert actual['/usr/share/nginx/previous']['source'] == str(c_root/'frontend')
    assert actual['/usr/share/nginx/previous']['read_only'] is True
    assert before == {str(p.relative_to(b_root)): p.read_bytes() for p in b_root.rglob('*') if p.is_file()}
    publish(w, 'asset-D')
    assert mounts()['/usr/share/nginx/previous']['source'] == str(b_root/'frontend')
    assert w.tool.load()['groups']['overseas'] == overseas
