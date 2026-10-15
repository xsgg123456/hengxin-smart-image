"""Fail closed on unsafe filesystem objects and test real cross-process fencing."""
import multiprocessing
import os
import subprocess
from types import SimpleNamespace

import pytest

from app.overseas.studio import context_fs as fs
from app.overseas.studio import context_workspace as context
from test_studio_context_assets import asset, original_path, workspace
from test_studio_context_migration import row, write


def symlink(link, target, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        pytest.skip('Symlink privilege is unavailable: ' + str(exc))


def test_legacy_hardlink_is_rejected_without_modifying_target(tmp_path):
    old = workspace(tmp_path)
    external = tmp_path / 'outside.txt'
    external.write_bytes(b'outside')
    os.link(external, old.work / 'linked.txt')
    current = workspace(tmp_path, old.home.parent.name)
    with pytest.raises(ValueError, match='linked'):
        context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    assert external.read_bytes() == b'outside'
    assert not (old.home.parent / 'persistent').exists()


@pytest.mark.parametrize('directory', [False, True])
def test_legacy_symlinks_are_never_followed(tmp_path, directory):
    old = workspace(tmp_path)
    target = tmp_path / 'outside'
    target.mkdir() if directory else target.write_bytes(b'outside')
    symlink(old.work / 'linked', target, directory)
    with pytest.raises(ValueError, match='links'):
        context.prepare(old, [row(old)], [], lambda _: pytest.fail())
    assert target.exists()


@pytest.mark.parametrize('name,directory', [('inputs', True), ('skills', True),
                                          ('input.json', False), ('.context-files.json', False)])
def test_work_mount_slots_cannot_redirect_platform_writes(tmp_path, name, directory):
    ws = workspace(tmp_path)
    context.prepare(ws, [], [], lambda _: pytest.fail())
    target = tmp_path / 'outside'
    target.mkdir() if directory else target.write_bytes(b'keep')
    slot = ws.work / name
    slot.rmdir() if directory else slot.unlink()
    symlink(slot, target, directory)
    with pytest.raises(ValueError, match='links'):
        context.prepare(ws, [], [], lambda _: pytest.fail())
    if not directory:
        assert target.read_bytes() == b'keep'


def test_registered_original_hardlink_is_not_repaired_by_writing_through_it(tmp_path):
    ws = workspace(tmp_path)
    item = asset()
    paths = context.prepare(ws, [], [item], lambda _: b'original')
    target = original_path(ws, paths[0])
    target.unlink()
    external = tmp_path / 'external'
    external.write_bytes(b'private!')
    os.link(external, target)
    with pytest.raises(ValueError, match='linked'):
        context.prepare(ws, [], [], lambda _: pytest.fail())
    assert external.read_bytes() == b'private!'


def test_disk_precheck_prevents_downloads_and_preserves_sources(tmp_path, monkeypatch):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'keep')
    current = workspace(tmp_path, old.home.parent.name)
    monkeypatch.setattr(fs.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='磁盘空间不足'):
        context.prepare(current, [row(old)], [asset()], lambda _: pytest.fail('must not download'))
    assert (old.work / 'notes.txt').read_bytes() == b'keep'
    assert not (old.home.parent / 'persistent').exists()


def test_store_outage_retains_existing_work_and_names_the_missing_original(tmp_path):
    ws = workspace(tmp_path)
    item = asset(name='missing-original.pdf')
    paths = context.prepare(ws, [], [item], lambda _: b'original')
    (ws.work / 'notes').write_text('keep')
    original_path(ws, paths[0]).unlink()
    def unavailable(_):
        raise OSError('storage offline')
    with pytest.raises(ValueError, match='missing-original.pdf'):
        context.prepare(ws, [], [], unavailable)
    assert (ws.work / 'notes').read_text() == 'keep'
    context.prepare(ws, [], [], lambda _: b'original')
    assert original_path(ws, paths[0]).read_bytes() == b'original'


def test_other_conversation_round_cannot_be_used(tmp_path):
    first, other = workspace(tmp_path), workspace(tmp_path)
    first.work = other.work
    with pytest.raises(ValueError, match='does not belong'):
        context.prepare(first, [], [], lambda _: pytest.fail())


def _competing_lock(root, queue):
    try:
        with fs.lock(root, timeout=0.2):
            queue.put('acquired')
    except ValueError:
        queue.put('blocked')


def test_lock_serializes_separate_processes_and_releases_afterward(tmp_path):
    root = fs.checked(workspace(tmp_path).home.parent)
    process_context = multiprocessing.get_context('spawn')
    queue = process_context.Queue()
    with fs.lock(root):
        process = process_context.Process(target=_competing_lock, args=(root, queue))
        process.start()
        process.join(10)
        assert not process.is_alive() and process.exitcode == 0
        assert queue.get(timeout=2) == 'blocked'
    process = process_context.Process(target=_competing_lock, args=(root, queue))
    process.start()
    process.join(10)
    assert not process.is_alive() and process.exitcode == 0
    assert queue.get(timeout=2) == 'acquired'
    queue.close()


@pytest.mark.skipif(os.name != 'posix', reason='FIFO only exists on POSIX')
def test_legacy_special_file_is_rejected_without_opening_it(tmp_path):
    old = workspace(tmp_path)
    os.mkfifo(old.work / 'pipe')
    with pytest.raises(ValueError, match='special'):
        context.prepare(old, [row(old)], [], lambda _: pytest.fail())


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction regression')
def test_windows_junction_cannot_import_an_external_directory(tmp_path):
    old = workspace(tmp_path)
    external = tmp_path / 'external-directory'
    external.mkdir()
    (external / 'private.txt').write_bytes(b'private')
    junction = old.work / 'junction'
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    try:
        assert junction.is_junction()
        with pytest.raises(ValueError, match='links'):
            context.prepare(old, [row(old)], [], lambda _: pytest.fail())
        assert (external / 'private.txt').read_bytes() == b'private'
    finally:
        junction.rmdir()
