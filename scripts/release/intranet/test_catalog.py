"""Catalog state-machine tests; Docker and artifact proof I/O are boundaries."""
import copy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import catalog
import catalog_import
import snapshot

REAL_PROOF = catalog.artifact_gc.proof


@pytest.fixture
def world(tmp_path, monkeypatch):
    root, state, releases = [tmp_path/name for name in ('lan', 'state', 'releases')]
    for path in (root, state, releases, state/'intranet-transactions'):
        path.mkdir()
    u = SimpleNamespace(ROOT=root, COMPOSE=root/'compose.json', safe=lambda *a: None)
    def report(name, data):
        path = state/name
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    store = SimpleNamespace(root=state, report=report)
    images = {'web': 'sha256:same', 'postgres': 'sha256:database'}
    monkeypatch.setattr(snapshot, 'RELEASES', releases)
    monkeypatch.setattr(catalog.image_gc, 'capture', lambda u: images.copy())
    monkeypatch.setattr(catalog.artifact_gc, 'proof', lambda u, s, p, k: {
        'path': str(p), 'kind': k, 'content': sorted(
            (str(f.relative_to(p)), snapshot.sha(f.read_bytes()))
            for f in p.rglob('*') if f.is_file()) if p.is_dir() else snapshot.sha(p.read_bytes())})
    def make(name, backend=None):
        source = releases/name
        source.mkdir()
        (source/'frontend').mkdir()
        work = state/'intranet-transactions'/name
        (work/'data-backup').mkdir(parents=True)
        (work/'data-backup/database.dump').write_bytes(b'backup-' + name.encode())
        raw = json.dumps({'services': {'domestic-web': {'volumes': [
            {'type': 'bind', 'source': str(source/'frontend'), 'target': '/usr/share/nginx/html'}]}}}).encode()
        (work/'compose.candidate.json').write_bytes(raw)
        (work/'web-before.json').write_bytes(raw)
        (work/'web-prepared.json').write_text(json.dumps({'candidate': snapshot.sha(raw), 'before': snapshot.sha(raw)}))
        (work/'applied.json').write_text('{}')
        current = dict(backend=str(backend or source), frontend=str(source), images={'web': images['web']}, data={'db': 'volume-one'})
        return current, dict(release=str(source), work=str(work), phase='deploying')
    a, item = make('A')
    data = dict(version=1, current=a, previous=None, pending=None, last=item)
    return SimpleNamespace(u=u, store=store, data=data, make=make, images=images, root=root)


def advance(w, data, name, backend=None):
    state, item = w.make(name, backend)
    completed = dict(data, current=state, previous=data['current'], last=item, pending=None)
    return catalog.advance(w.u, w.store, data, completed, item)


def test_same_images_advance_success_clock_and_transaction_protection(world):
    w = world
    a = catalog.bootstrap(w.u, w.store, w.data)
    b = advance(w, a, 'B', backend=a['current']['backend'])
    c = advance(w, b, 'C', backend=a['current']['backend'])
    assert c['retention']['current']['images'] == c['retention']['previous']['images']
    assert c['retention']['current']['state_sha256'] == catalog.state_sha(c['current'])
    assert c['retention']['previous']['state_sha256'] == catalog.state_sha(b['current'])
    sources, paths = catalog.protected(c)
    assert a['current']['backend'] in sources  # Shared backend A remains live.
    assert paths == {b['last']['work'], c['last']['work']}
    old = c['retention']['artifacts'][a['last']['work']]
    assert set(old['owners']).isdisjoint(sources)  # A backup does not inherit source lifetime.
    assert b['last']['work'] in sources and c['last']['work'] in sources
    assert a['retention']['previous'] is None  # No mutation of prior saved catalog.


@pytest.mark.skipif(os.name == 'nt', reason='Real descriptor deletion and allocated blocks require Linux')
def test_real_gc_deletes_A_backup_but_keeps_shared_A_source_and_B_C_backups(world, monkeypatch):
    w = world
    gc = catalog.artifact_gc
    monkeypatch.setattr(gc, 'proof', REAL_PROOF)
    monkeypatch.setattr(gc.cleanup_refs, 'host', lambda *a: {})
    a = catalog.bootstrap(w.u, w.store, w.data)
    package = w.root/'shared-A.tar.gz'
    package.write_bytes(b'original shared backend source package')
    catalog.add_artifact(w.u, w.store, a['retention'], package, 'package', [a['current']['backend']])
    b = advance(w, a, 'B', backend=a['current']['backend'])
    c = advance(w, b, 'C', backend=a['current']['backend'])
    protected_sources, protected_paths = catalog.protected(c)
    result = gc.execute(w.u, w.store, c['retention']['artifacts'], protected_sources, protected_paths, apply=True)
    assert result['status'] == 'complete' and result['deleted'] == [a['last']['work']]
    assert not Path(a['last']['work']).exists()
    assert Path(a['current']['backend']).exists() and package.exists()
    for retained in (b, c):
        assert (Path(retained['last']['work'])/'data-backup/database.dump').exists()


@pytest.mark.parametrize('which', ['current', 'previous'])
def test_catalog_state_drift_rejected(world, which):
    w = world
    data = advance(w, catalog.bootstrap(w.u, w.store, w.data), 'B')
    data[which]['frontend'] += '-tampered'
    with pytest.raises(RuntimeError, match='catalog drift'):
        catalog.check(data)


def test_full_fleet_drift_refuses_before_and_advance_without_mutating_catalog(world):
    w = world
    data = catalog.bootstrap(w.u, w.store, w.data)
    saved = copy.deepcopy(data)
    w.images['postgres'] = 'sha256:unexpected-upgrade'
    with pytest.raises(RuntimeError, match='fleet drift'):
        catalog.before(w.u, w.store, data)
    with pytest.raises(RuntimeError, match='Runtime images changed'):
        advance(w, data, 'B')
    assert data == saved


@pytest.mark.parametrize('matches', [0, 2])
def test_bootstrap_refuses_unknown_or_ambiguous_previous_transaction(world, matches):
    w = world
    previous = copy.deepcopy(w.data['current'])
    current, item = w.make('B')
    w.data.update(current=current, previous=previous, last=item)
    old = Path(w.store.root/'intranet-transactions/A')
    if matches == 0:
        (old/'applied.json').unlink()
    else:
        duplicate = old.parent/'A-duplicate'
        duplicate.mkdir()
        for name in ('web-prepared.json', 'compose.candidate.json', 'applied.json'):
            (duplicate/name).write_bytes((old/name).read_bytes())
    with pytest.raises(RuntimeError, match='cannot be identified'):
        catalog.bootstrap(w.u, w.store, w.data)
    assert 'retention' not in w.data


def test_bootstrap_refuses_different_previous_data_identity(world):
    w = world
    previous = dict(w.data['current'], data={'db': 'different-volume'})
    w.data['previous'] = previous
    with pytest.raises(RuntimeError, match='explicit upgrade inventory'):
        catalog.bootstrap(w.u, w.store, w.data)


def test_bootstrap_identifies_previous_and_keeps_unknown_artifacts_unowned(world):
    w = world
    previous = w.data['current']
    current, item = w.make('B')
    w.data.update(current=current, previous=previous, last=item)
    unknown = w.store.root/'intranet-transactions/unfinished'
    unknown.mkdir()
    (unknown/'database.dump').write_bytes(b'unknown ownership')
    data = catalog.bootstrap(w.u, w.store, w.data)
    assert data['retention']['previous']['work'] == str(unknown.parent/'A')
    assert str(unknown) in data['retention']['unowned']
    assert str(unknown) not in data['retention']['artifacts']


def test_staged_package_is_protected_by_source_and_success_clears_stage(world):
    w = world
    data = catalog.bootstrap(w.u, w.store, w.data)
    state, item = w.make('B')
    archive = w.root/'B.tar.gz'
    archive.write_bytes(b'package')
    catalog.stage(w.u, w.store, data, item['release'], archive)
    assert item['release'] in catalog.protected(data)[0]
    completed = dict(data, current=state, previous=data['current'], last=item)
    catalog.advance(w.u, w.store, data, completed, item)
    assert not completed['retention']['staged']
    assert completed['retention']['artifacts'][str(archive)]['owners'] == [item['release']]


def test_import_rejects_candidate_digest_drift_and_ignores_rolled_back_work(world):
    work = Path(world.data['last']['work'])
    (work/'compose.candidate.json').write_bytes(b'tampered')
    with pytest.raises(RuntimeError, match='candidate drift'):
        catalog_import.transaction(world.u, work)
    (work/'rolled-back.json').write_text('{}')
    assert catalog_import.transaction(world.u, work) is None


def test_recovery_restores_previous_catalog_without_new_success(world):
    w = world
    a = catalog.bootstrap(w.u, w.store, w.data)
    b = advance(w, a, 'B')
    b.update(current=a['current'], previous=None, last=None)
    catalog.recover(b)
    assert b['retention']['current'] == a['retention']['current']
    assert b['retention']['previous'] is None


def test_bootstrap_requires_applied_evidence_for_current_work(world):
    (Path(world.data['last']['work'])/'applied.json').unlink()
    with pytest.raises(RuntimeError, match='Current successful transaction'):
        catalog.bootstrap(world.u, world.store, world.data)


def test_import_package_checks_real_bytes_not_just_manifest(world, monkeypatch):
    import io
    import tarfile
    w = world
    files = {'frontend/index.html': snapshot.sha(b'expected')}
    manifest = {'commit': 'a'*40, 'files': files}
    monkeypatch.setattr(snapshot, 'manifest', lambda *a: manifest)
    path = w.root/'bad.tar.gz'
    with tarfile.open(path, 'w:gz') as tar:
        for name, raw in [('release-manifest.json', json.dumps(manifest).encode()),
                          ('frontend/index.html', b'tampered')]:
            item = tarfile.TarInfo(name)
            item.size = len(raw)
            tar.addfile(item, io.BytesIO(raw))
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        catalog_import.package(w.u, path, {w.data['current']['frontend']})


def test_legacy_backup_requires_all_config_and_database_provenance(world, monkeypatch):
    w = world
    w.u.NATIVE = {str(i): None for i in range(7)}
    backup = w.root/'unified-backup-test'
    backup.mkdir()
    keys = {'/etc/hengxin-lan/' + n + '.env': n for n in w.u.NATIVE}
    (backup/'preserved-hashes.json').write_text(json.dumps(keys))
    (backup/'accounts.tar').write_bytes(b'accounts')
    prepared = {'configs': [{'path': k, 'sha256': v} for k, v in keys.items()], 'data_containers': {}}
    summary = {'accounts_bytes': 8}
    for side in ('domestic', 'overseas'):
        (backup/(side+'.dump')).write_bytes(b'dump')
        prepared['data_containers'][side+'-postgres'] = side+'-id'
        summary[side] = {'archive_valid': True, 'container_id': side+'-id', 'bytes': 4, 'sha256': snapshot.sha(b'dump')}
    (backup/'summary.json').write_text(json.dumps(summary))
    monkeypatch.setattr(catalog_import.artifact_gc, 'digest', lambda p: snapshot.sha(p.read_bytes()))
    assert catalog_import.backup_matches(w.u, backup, prepared)
    (backup/'domestic.dump').write_bytes(b'evil')
    assert not catalog_import.backup_matches(w.u, backup, prepared)
    (backup/'domestic.dump').write_bytes(b'dump')
    keys.pop(next(iter(keys)))
    (backup/'preserved-hashes.json').write_text(json.dumps(keys))
    assert not catalog_import.backup_matches(w.u, backup, prepared)
