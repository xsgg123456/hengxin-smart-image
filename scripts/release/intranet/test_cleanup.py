"""Real isolated filesystem retention, with external services replaced at the boundary."""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import cleanup
import cleanup_history
import cleanup_pending
import cleanup_refs
import engine
import release
import snapshot

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='Linux filesystem permissions and /proc semantics')


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / 'releases'
    root.mkdir()
    monkeypatch.setattr(snapshot, 'RELEASES', root)
    def safe(path, **kwargs):
        for p in (path, *path.parents):
            if p == tmp_path.parent:
                break
            s = p.lstat()
            if stat.S_ISLNK(s.st_mode) or (os.name != 'nt' and s.st_mode & 0o022):
                raise RuntimeError('Unsafe test path')
    monkeypatch.setattr(engine.u, 'safe', safe)
    def make(name):
        p = root / name
        (p / 'backend/app/execution').mkdir(parents=True)
        (p / 'frontend').mkdir()
        renderer = p / 'backend/app/execution/office_render.py'
        renderer.write_bytes(b'print(1)')
        renderer.chmod(0o755)
        (p / 'frontend/index.html').write_bytes(b'index')
        files = {q.relative_to(p).as_posix(): snapshot.sha(q.read_bytes())
                 for q in p.rglob('*') if q.is_file()}
        (p / 'release-manifest.json').write_text(json.dumps({'commit': 'a'*40, 'files': files}))
        return p
    old, previous, current = [make(n) for n in ('old', 'previous', 'current')]
    data = dict(current=dict(backend=str(current), frontend=str(current)),
                previous=dict(backend=str(previous), frontend=str(previous)), pending=None,
                source_history=[str(old), str(previous), str(current)])
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: data['current'])
    def refs(u, ledger, root):
        result = cleanup_refs.References(root)
        cleanup_refs.ledger_refs(result, ledger)
        return {k: sorted(v) for k, v in result.reasons.items()}
    monkeypatch.setattr(cleanup_refs, 'collect', refs)
    store = release.retention_store(tmp_path / 'state')
    return SimpleNamespace(root=root, old=old, previous=previous, current=current,
                           data=data, store=store, u=engine.u, make=make, refs=refs)


def test_preview_retains_split_frontend_and_backend_and_unknown_candidate(world):
    w = world
    w.data['current']['backend'] = str(w.previous)
    candidate = w.make('not-yet-published')
    report = cleanup.execute(w.u, w.store, w.data)
    assert [r['path'] for r in report['candidates']] == [str(w.old)]
    assert set(report['kept']) == {str(w.current), str(w.previous), str(candidate)}
    assert w.old.exists() and not (w.store.root/'intranet-cleanup.json').exists()


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason='Real fd deletion requires Linux')
def test_delete_only_old_and_measure_actual_blocks_and_repeat(world):
    w = world
    before = cleanup.tree_size(w.root) + cleanup.tree_size(w.store.root)
    result = cleanup.execute(w.u, w.store, w.data, apply=True)
    after = cleanup.tree_size(w.root) + cleanup.tree_size(w.store.root)
    assert result['deleted'] == [str(w.old)] and result['status'] == 'complete'
    assert w.previous.exists() and w.current.exists() and not w.old.exists()
    assert result['net_released_bytes'] == before - after
    assert cleanup.execute(w.u, w.store, w.data, apply=True)['deleted'] == []


@pytest.mark.parametrize('pending', [{'phase': 'prepared'}, {'phase': 'deploying'}, {'phase': 'recovered'}])
def test_pending_never_collects_or_deletes(world, monkeypatch, pending):
    world.data['pending'] = pending
    monkeypatch.setattr(cleanup_refs, 'collect', lambda *a: pytest.fail('must not plan'))
    with pytest.raises(RuntimeError, match='Pending'):
        cleanup.execute(world.u, world.store, world.data, apply=True)


def test_baseline_drift_and_reference_inspection_failure_prevent_deletion(world, monkeypatch):
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: {})
    with pytest.raises(RuntimeError, match='drift'):
        cleanup.execute(world.u, world.store, world.data, apply=True)
    monkeypatch.setattr(snapshot, 'capture', lambda *a, **k: world.data['current'])
    monkeypatch.setattr(cleanup_refs, 'collect', lambda *a: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        cleanup.execute(world.u, world.store, world.data, apply=True)
    assert world.old.exists()


@pytest.mark.parametrize('reason', ['container-mount', 'process-fd', 'systemd-config', 'host-mount'])
def test_in_use_old_directory_is_retained(world, monkeypatch, reason):
    def refs(*args):
        result = world.refs(*args)
        result[str(world.old)] = [reason]
        return result
    monkeypatch.setattr(cleanup_refs, 'collect', refs)
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']


@pytest.mark.parametrize('name', ['backend/.venv', 'backend/node_modules', 'unknown.txt'])
def test_dependency_or_unknown_file_is_not_deleted(world, name):
    path = world.old / name
    if name == 'unknown.txt':
        path.write_text('data')
    else:
        path.mkdir()
    result = cleanup.execute(world.u, world.store, world.data)
    assert not result['candidates'] and world.old.exists()


def test_legacy_compatibility_manifest_is_allowed_only_when_matching(world):
    legacy = world.old/'compatibility-files.json'
    legacy.write_text('{}')
    assert len(cleanup.execute(world.u, world.store, world.data)['candidates']) == 1
    legacy.write_text('{"outside": "bad"}')
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']


@pytest.mark.skipif(os.name == 'nt', reason='Linux links/permissions are the deployment boundary')
def test_symlink_and_writable_tree_and_mount_are_retained(world, monkeypatch):
    outside = world.root.parent/'outside'
    outside.write_text('keep')
    link = world.old/'backend/link'
    link.symlink_to(outside)
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']
    link.unlink()
    world.old.chmod(0o777)
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']
    world.old.chmod(0o755)
    monkeypatch.setattr(os.path, 'ismount', lambda p: p == world.old/'backend')
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']
    assert outside.read_text() == 'keep'


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason='Real fd deletion requires Linux')
def test_new_reference_between_plan_and_delete_is_respected(world, monkeypatch):
    count = 0
    def refs(*args):
        nonlocal count
        count += 1
        result = world.refs(*args)
        if count > 1:
            result[str(world.old)] = ['new-container']
        return result
    monkeypatch.setattr(cleanup_refs, 'collect', refs)
    assert cleanup.execute(world.u, world.store, world.data, apply=True)['deleted'] == []
    assert world.old.exists()


@pytest.mark.skipif(not shutil.rmtree.avoids_symlink_attacks, reason='Real fd deletion requires Linux')
def test_delete_error_is_recorded_and_does_not_change_ledger(world, monkeypatch):
    world.store.report('intranet.json', world.data)
    before = (world.store.root/'intranet.json').read_bytes()
    def fail(*a, **k):
        raise OSError('cannot delete')
    monkeypatch.setattr(cleanup.shutil, 'rmtree', fail)
    fail.avoids_symlink_attacks = True
    report = cleanup.execute(world.u, world.store, world.data, apply=True)
    assert report['status'] == 'warning' and world.old.exists()
    assert (world.store.root/'intranet.json').read_bytes() == before


def test_previous_interpreter_protects_older_source(world):
    world.data['previous']['native'] = {'worker': {'python': str(world.old/'backend/.venv/bin/python')}}
    assert not cleanup.execute(world.u, world.store, world.data)['candidates']


def test_upgrade_discovers_checksum_bound_old_compose(world):
    world.data['source_history'] = []
    work = world.store.root/'intranet-transactions/old-tx'
    work.mkdir(parents=True)
    raw = json.dumps({'services': {'api': {'volumes': [{'type': 'bind',
        'source': str(world.old/'backend/app'), 'target': '/app/app'}]}}}).encode()
    (work/'web-before.json').write_bytes(raw)
    (work/'web-prepared.json').write_text(json.dumps({'before': snapshot.sha(raw)}))
    (work/'applied.json').write_text('{}')
    assert str(world.old) in cleanup_history.known(world.u, world.store, world.data)
    (work/'web-before.json').write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='drift'):
        cleanup.execute(world.u, world.store, world.data, apply=True)


def test_partial_delete_can_resume_without_manifest(world, monkeypatch):
    original = cleanup.shutil.rmtree
    def partial(name, dir_fd=None):
        (world.old/'release-manifest.json').unlink()
        (world.old/'frontend/index.html').unlink()
        raise OSError('interrupted after removing files')
    partial.avoids_symlink_attacks = True
    monkeypatch.setattr(cleanup.shutil, 'rmtree', partial)
    first = cleanup.execute(world.u, world.store, world.data, apply=True)
    assert first['status'] == 'warning'
    assert (world.store.root/cleanup_pending.NAME).exists()
    monkeypatch.setattr(cleanup.shutil, 'rmtree', original)
    second = cleanup.execute(world.u, world.store, world.data, apply=True)
    assert second['deleted'] == [str(world.old)] and second['status'] == 'complete'
    assert not (world.store.root/cleanup_pending.NAME).exists()


@pytest.mark.parametrize('tamper', ['added', 'changed', 'identity'])
def test_partial_cleanup_proof_rejects_new_or_changed_content(world, tamper):
    proof = cleanup_pending.inventory(world.u, world.old)
    world.store.report(cleanup_pending.NAME, proof)
    (world.old/'release-manifest.json').unlink()
    if tamper == 'added':
        (world.old/'new-file').write_text('do not delete')
    elif tamper == 'changed':
        (world.old/'frontend/index.html').write_text('changed')
    else:
        proof['identity'][1] += 1
        world.store.report(cleanup_pending.NAME, proof)
    with pytest.raises(RuntimeError, match='drift'):
        cleanup.execute(world.u, world.store, world.data, apply=True)
    assert world.old.exists()
