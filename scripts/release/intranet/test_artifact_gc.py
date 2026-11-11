"""Artifact retention uses isolated real files; host reference boundaries are stubbed."""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import artifact_gc as gc

pytestmark = pytest.mark.skipif(os.name == 'nt', reason='POSIX descriptor deletion and block accounting')


@pytest.fixture
def world(tmp_path, monkeypatch):
    root, state = tmp_path/'lan', tmp_path/'state'
    root.mkdir()
    state.mkdir(mode=0o700)
    (state/'intranet-transactions').mkdir(mode=0o700)
    def safe(path):
        for item in (path, *path.parents):
            if item == tmp_path.parent:
                break
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022:
                raise RuntimeError('Unsafe path')
    def report(name, data):
        path = state/name
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    u, store = SimpleNamespace(ROOT=root, safe=safe), SimpleNamespace(root=state, report=report)
    monkeypatch.setattr(gc.cleanup_refs, 'host', lambda *args: {}, raising=False)
    registry = {}
    def make(name, kind='package', owners=None):
        path = (state/'intranet-transactions' if kind == 'transaction' else root)/name
        if kind == 'package':
            path.write_bytes(b'archive'*1000)
        else:
            (path/'data-backup').mkdir(parents=True)
            (path/'data-backup/database.dump').write_bytes(b'dump'*3000)
            (path/'config').write_text('private config')
        registry[str(path)] = {'owners': owners or ['/source/old'], 'proof': gc.proof(u, store, path, kind)}
        return path
    return SimpleNamespace(root=root, store=store, u=u, registry=registry, make=make)


def execute(w, apply=False, sources=(), paths=()):
    return gc.execute(w.u, w.store, w.registry, set(sources), set(paths), apply)


def test_preview_has_no_writes_and_unknown_files_stay(world):
    w = world
    old = w.make('old.tgz')
    unknown = w.root/'unknown.tgz'
    unknown.write_text('keep')
    before = list(w.store.root.iterdir())
    result = execute(w)
    assert result['candidates'] == [str(old)] and result['status'] == 'preview'
    assert list(w.store.root.iterdir()) == before and old.exists() and unknown.exists()


def test_package_and_transaction_delete_without_copies_and_exact_blocks(world, monkeypatch):
    w = world
    package, tx = w.make('old.tar.gz'), w.make('old-tx', 'transaction')
    before = gc.allocated([package, tx])
    monkeypatch.setattr(shutil, 'copytree', lambda *a, **k: pytest.fail('must not copy'))
    monkeypatch.setattr(shutil, 'copy2', lambda *a, **k: pytest.fail('must not copy'))
    result = execute(w, True)
    assert set(result['deleted']) == {str(package), str(tx)}
    assert result['status'] == 'complete' and result['released_bytes'] == before
    assert result['after_bytes'] == 0 and not package.exists() and not tx.exists()
    assert execute(w, True)['deleted'] == []


@pytest.mark.parametrize('owner', ['/source/current', '/source/previous', '/source/staged'])
def test_shared_package_retained_by_any_protected_owner(world, owner):
    path = world.make('shared.tgz', owners=['/source/old', owner])
    result = execute(world, True, sources=[owner])
    assert str(path) in result['kept'] and path.exists() and not result['deleted']


@pytest.mark.parametrize('reference', ['self', 'child', 'parent'])
def test_current_previous_transaction_and_ancestor_refs_stay(world, reference):
    tx = world.make('last-tx', 'transaction')
    protected = {'self': tx, 'child': tx/'data-backup/database.dump', 'parent': tx.parent}[reference]
    assert str(tx) in execute(world, True, paths=[str(protected)])['kept']
    assert tx.exists()


@pytest.mark.parametrize('reason', ['process-fd', 'container-mount', 'systemd-config', 'host-mount'])
def test_live_references_keep_artifacts(world, monkeypatch, reason):
    path = world.make('used.tgz')
    monkeypatch.setattr(gc.cleanup_refs, 'host', lambda *a: {str(path): [reason]})
    assert str(path) in execute(world, True)['kept'] and path.exists()


def test_new_live_reference_at_delete_boundary_stops_item(world, monkeypatch):
    path = world.make('race.tgz')
    calls = []
    def refs(*args):
        calls.append(1)
        return {} if len(calls) == 1 else {str(path): ['new-process']}
    monkeypatch.setattr(gc.cleanup_refs, 'host', refs)
    result = execute(world, True)
    assert result['status'] == 'warning' and not result['deleted'] and path.exists()


def test_partial_failure_keeps_original_proof_and_other_items_continue(world, monkeypatch):
    w = world
    tx, package = w.make('old-tx', 'transaction'), w.make('old.tgz')
    original = gc.shutil.rmtree
    def partial(name, dir_fd=None):
        (tx/'config').unlink()
        raise OSError('isolated failure')
    partial.avoids_symlink_attacks = True
    monkeypatch.setattr(gc.shutil, 'rmtree', partial)
    result = execute(w, True)
    pending = json.loads((w.store.root/gc.PENDING).read_text())
    assert result['status'] == 'warning' and not package.exists() and tx.exists()
    assert pending[str(tx)] == w.registry[str(tx)]['proof']
    monkeypatch.setattr(gc.shutil, 'rmtree', original)
    assert execute(w, True)['deleted'] == [str(tx)] and not tx.exists()
    assert json.loads((w.store.root/gc.PENDING).read_text()) == {}


@pytest.mark.parametrize('tamper', ['new', 'changed', 'identity', 'registry'])
def test_partial_retry_rejects_tampering_without_losing_proof(world, tamper):
    w = world
    tx = w.make('partial-tx', 'transaction')
    original = w.registry[str(tx)]['proof']
    w.store.report(gc.PENDING, {str(tx): original})
    (tx/'config').unlink()
    if tamper == 'new':
        (tx/'new').write_text('new')
    elif tamper == 'changed':
        (tx/'data-backup/database.dump').write_text('changed')
    elif tamper == 'identity':
        w.store.report(gc.PENDING, {str(tx): dict(original, identity=[-1, -1])})
    else:
        w.registry[str(tx)]['proof'] = gc.proof(w.u, w.store, tx, 'transaction')
    expected = (w.store.root/gc.PENDING).read_bytes()
    result = execute(w, True)
    assert result['status'] == 'warning' and tx.exists()
    assert (w.store.root/gc.PENDING).read_bytes() == expected


@pytest.mark.parametrize('unsafe', ['link', 'hardlink', 'writable', 'dependency', 'mount', 'outside'])
def test_proof_rejects_unsafe_content(world, monkeypatch, unsafe):
    w = world
    tx = w.make('unsafe-tx', 'transaction')
    if unsafe == 'link':
        (tx/'link').symlink_to(w.root)
    elif unsafe == 'hardlink':
        os.link(tx/'config', tx/'alias')
    elif unsafe == 'writable':
        (tx/'config').chmod(0o666)
    elif unsafe == 'dependency':
        (tx/'data-backup/venv').mkdir()
    elif unsafe == 'mount':
        monkeypatch.setattr(os.path, 'ismount', lambda p: p == tx/'data-backup')
    else:
        tx = w.root/'not-a-transaction'
        tx.mkdir()
    with pytest.raises(RuntimeError):
        gc.proof(w.u, w.store, tx, 'transaction')


def test_unknown_legacy_name_and_noncanonical_path_rejected(world):
    w = world
    legacy = w.make('unify-known', 'legacy')
    assert execute(w, True)['deleted'] == [str(legacy)]
    with pytest.raises(RuntimeError):
        gc.proof(w.u, w.store, str(w.root)+'/../lan/fake.tgz', 'package')
    with pytest.raises(RuntimeError):
        gc.proof(w.u, w.store, w.root/'independent-backup', 'legacy')


def test_same_filesystem_bind_mount_is_rejected(world, monkeypatch):
    tx = world.make('bind-tx', 'transaction')
    original = Path.read_text
    def contents(path, *args, **kwargs):
        if path == Path('/proc/self/mountinfo'):
            return f'1 2 0:1 / {tx}/data-backup rw - ext4 /dev/test rw\n'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', contents)
    monkeypatch.setattr(os.path, 'ismount', lambda p: False)
    with pytest.raises(RuntimeError, match='Mounted'):
        gc.proof(world.u, world.store, tx, 'transaction')


def test_stream_hash_and_nested_measurement_no_double_count(world, monkeypatch):
    path = world.make('stream.tgz')
    monkeypatch.setattr(Path, 'read_bytes', lambda *a: pytest.fail('must stream hash'))
    assert gc.proof(world.u, world.store, path, 'package')['files']['.']
    tx = world.make('sized-tx', 'transaction')
    assert gc.allocated([tx, tx/'data-backup', tx]) == gc.allocated([tx])


def test_missing_registry_does_not_discard_outstanding_pending_proof(world):
    path = world.make('pending-tx', 'transaction')
    world.store.report(gc.PENDING, {str(path): world.registry[str(path)]['proof']})
    world.registry.clear()
    execute(world, True)
    assert str(path) in json.loads((world.store.root/gc.PENDING).read_text())


def test_failed_reference_inspection_does_not_delete(world, monkeypatch):
    path = world.make('keep.tgz')
    def failure(*a):
        raise PermissionError('cannot read references')
    monkeypatch.setattr(gc.cleanup_refs, 'host', failure)
    result = execute(world, True)
    assert result['status'] == 'warning' and path.exists() and not result['deleted']
