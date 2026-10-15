"""Incremental legacy recovery preserves files created in persistent work."""
import hashlib

import pytest

from app.overseas.studio import context_fs as fs
from app.overseas.studio import context_workspace as context
from test_studio_context_assets import workspace
from test_studio_context_migration import index, row, write


def restored(ws):
    result = {}
    for item in index(ws)['files']:
        content = (ws.work / item['path'].removeprefix('/work/')).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item['sourceChecksum']
        result.setdefault(item['logicalPath'], set()).add(content)
    return result


def prepared(tmp_path):
    current = workspace(tmp_path)
    context.prepare(current, [], [], lambda _: pytest.fail())
    rollback = workspace(tmp_path, current.home.parent.name)
    return current, rollback


def test_new_work_file_and_rollback_version_are_both_indexed(tmp_path):
    current, rollback = prepared(tmp_path)
    write(current.work, 'new.txt', b'created in persistent work')
    write(rollback.work, 'new.txt', b'created after rollback')
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {'/work/new.txt': {
        b'created in persistent work', b'created after rollback'}}
    assert all(item['conflict'] for item in index(current)['files'])
    assert not (current.work / 'new.txt').exists()
    assert (rollback.work / 'new.txt').read_bytes() == b'created after rollback'
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert len(index(current)['files']) == 2


def test_edited_registered_work_file_conflicts_with_identical_historical_versions(tmp_path):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'historical original')
    current = workspace(tmp_path, old.home.parent.name)
    context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    write(current.work, 'notes.txt', b'current model edits')
    rollback = workspace(tmp_path, old.home.parent.name)
    write(rollback.work, 'notes.txt', b'historical original')
    context.prepare(current, [row(old), row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {'/work/notes.txt': {
        b'historical original', b'current model edits'}}
    assert len(index(current)['files']) == 3
    assert all(item['conflict'] for item in index(current)['files'])
    assert not (current.work / 'notes.txt').exists()


def test_identical_work_file_is_reused_without_duplicate_or_conflict(tmp_path):
    current, rollback = prepared(tmp_path)
    existing = write(current.work, 'new.txt', b'same content')
    before = existing.stat().st_mtime_ns
    write(rollback.work, 'new.txt', b'same content')
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {'/work/new.txt': {b'same content'}}
    assert len(index(current)['files']) == 1
    assert not index(current)['files'][0]['conflict']
    assert existing.stat().st_mtime_ns == before


@pytest.mark.parametrize('existing,incoming', [
    ('result', 'result/design.png'),
    ('result/design.png', 'result'),
    ('result/research/deep/design.png', 'result'),
])
def test_current_work_and_legacy_directory_prefix_conflicts(tmp_path, existing, incoming):
    current, rollback = prepared(tmp_path)
    write(current.work, existing, b'current working content')
    write(rollback.work, incoming, b'rollback content')
    unrelated = write(current.work, 'unrelated/keep.txt', b'leave this alone')
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {
        '/work/' + existing: {b'current working content'},
        '/work/' + incoming: {b'rollback content'},
    }
    assert all(item['conflict'] for item in index(current)['files'])
    assert not (current.work / 'result').exists()
    assert unrelated.read_bytes() == b'leave this alone'


def test_current_empty_directory_does_not_block_legacy_file_recovery(tmp_path):
    current, rollback = prepared(tmp_path)
    fs.mkdir(current.work / 'result')
    write(rollback.work, 'result', b'rollback file')
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {'/work/result': {b'rollback file'}}
    assert index(current)['files'][0]['conflict']
    assert not (current.work / 'result').exists()


@pytest.mark.parametrize('failure', ['context-index.json', 'manifest.json'])
@pytest.mark.parametrize('existing', ['new.txt', 'new.txt/research/notes.txt'])
def test_retry_after_metadata_failure_preserves_unregistered_work_version(
        tmp_path, monkeypatch, failure, existing):
    current, rollback = prepared(tmp_path)
    write(current.work, existing, b'precious current work')
    write(rollback.work, 'new.txt', b'rollback file')
    save = fs.save
    def fail_metadata(path, data):
        if path.name == failure:
            raise OSError('metadata failure')
        return save(path, data)
    monkeypatch.setattr(fs, 'save', fail_metadata)
    with pytest.raises(OSError, match='metadata failure'):
        context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert not (current.work / 'new.txt').exists()
    assert (current.work.parent / 'migration-pending.json').exists()
    monkeypatch.setattr(fs, 'save', save)
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    expected = {'/work/new.txt': {b'rollback file'}}
    expected.setdefault('/work/' + existing, set()).add(b'precious current work')
    assert restored(current) == expected
    assert all(item['conflict'] for item in index(current)['files'])
    assert not (current.work.parent / 'migration-pending.json').exists()


def test_current_directory_symlink_collision_fails_closed(tmp_path):
    from test_studio_context_safety import symlink
    current, rollback = prepared(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    private = write(outside, 'private.txt', b'never import')
    symlink(current.work / 'result', outside, directory=True)
    write(rollback.work, 'result/new.txt', b'rollback file')
    with pytest.raises(ValueError, match='links'):
        context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert private.read_bytes() == b'never import'
    assert index(current)['files'] == []


def test_current_work_version_survives_copy_interruption_before_alias_removal(tmp_path, monkeypatch):
    current, rollback = prepared(tmp_path)
    write(current.work, 'new.txt', b'current work')
    write(rollback.work, 'new.txt', b'rollback file')
    copy = fs.copy
    count = 0
    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('copy interrupted')
        return copy(*args, **kwargs)
    monkeypatch.setattr(fs, 'copy', fail_second)
    with pytest.raises(OSError, match='copy interrupted'):
        context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert (current.work / 'new.txt').read_bytes() == b'current work'
    monkeypatch.setattr(fs, 'copy', copy)
    context.prepare(current, [row(rollback)], [], lambda _: pytest.fail())
    assert restored(current) == {'/work/new.txt': {b'current work', b'rollback file'}}
    assert all(item['conflict'] for item in index(current)['files'])
