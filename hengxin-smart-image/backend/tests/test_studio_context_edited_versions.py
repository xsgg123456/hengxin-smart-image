"""Mapped recovery files stay editable across incremental imports and retries."""
import pytest

from app.overseas.studio import context_fs as fs
from app.overseas.studio import context_workspace as context
from test_studio_context_assets import workspace
from test_studio_context_migration import index, row, write
from test_studio_context_work_conflicts import restored


def edited_recovery(tmp_path):
    first = workspace(tmp_path)
    second = workspace(tmp_path, first.home.parent.name)
    write(first.work, 'notes.txt', b'history one')
    write(second.work, 'notes.txt', b'history two')
    current = workspace(tmp_path, first.home.parent.name)
    history = [row(first), row(second)]
    context.prepare(current, history, [], lambda _: pytest.fail())
    entry = next(item for item in index(current)['files']
                 if item['sources'] == [first.work.name])
    edited = current.work / entry['path'].removeprefix('/work/')
    edited.write_bytes(b'edited recovery')
    return current, history, edited, first, second


def add_rollback(current, history, name, content):
    rollback = workspace(current.home.parent.parent, current.home.parent.name)
    write(rollback.work, name, content)
    history.append(row(rollback))
    return rollback


def assert_versions(current, history_sources, expected):
    assert restored(current) == expected
    for source, content in history_sources:
        assert (source.work / 'notes.txt').read_bytes() == content


def test_edited_recovered_path_allows_unrelated_incremental_import(tmp_path):
    current, history, edited, first, second = edited_recovery(tmp_path)
    add_rollback(current, history, 'unrelated.txt', b'new round')
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'edited recovery'
    assert_versions(current, [(first, b'history one'), (second, b'history two')], {
        '/work/notes.txt': {b'history one', b'history two', b'edited recovery'},
        '/work/unrelated.txt': {b'new round'},
    })


def test_same_history_reconciles_index_without_undoing_edit(tmp_path):
    current, history, edited, first, second = edited_recovery(tmp_path)
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'edited recovery'
    assert_versions(current, [(first, b'history one'), (second, b'history two')], {
        '/work/notes.txt': {b'history one', b'history two', b'edited recovery'},
    })


def test_workspace_version_can_be_edited_again_before_next_increment(tmp_path):
    current, history, edited, first, second = edited_recovery(tmp_path)
    add_rollback(current, history, 'unrelated.txt', b'new round')
    context.prepare(current, history, [], lambda _: pytest.fail())
    edited.write_bytes(b'edited again')
    add_rollback(current, history, 'another.txt', b'another round')
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'edited again'
    assert_versions(current, [(first, b'history one'), (second, b'history two')], {
        '/work/notes.txt': {b'history one', b'history two', b'edited again'},
        '/work/unrelated.txt': {b'new round'}, '/work/another.txt': {b'another round'},
    })


@pytest.mark.parametrize('edit_before_retry', [False, True])
@pytest.mark.parametrize('failure', ['context-index.json', 'manifest.json', 'copy'])
def test_edited_mapping_survives_interruption_and_retry(
        tmp_path, monkeypatch, failure, edit_before_retry):
    current, history, edited, first, second = edited_recovery(tmp_path)
    add_rollback(current, history, 'unrelated.txt', b'new round')
    save, copy = fs.save, fs.copy
    count = 0
    def fail_save(path, data):
        if path.name == failure:
            raise OSError('interrupted migration')
        return save(path, data)
    def fail_second_copy(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('interrupted migration')
        return copy(*args, **kwargs)
    monkeypatch.setattr(fs, 'save', fail_save)
    if failure == 'copy':
        monkeypatch.setattr(fs, 'copy', fail_second_copy)
    with pytest.raises(OSError, match='interrupted migration'):
        context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'edited recovery'
    assert (current.work.parent / 'migration-pending.json').exists()
    expected_edit = b'edited during interrupted migration' if edit_before_retry else b'edited recovery'
    if edit_before_retry:
        edited.write_bytes(expected_edit)
    monkeypatch.setattr(fs, 'save', save)
    monkeypatch.setattr(fs, 'copy', copy)
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == expected_edit
    assert_versions(current, [(first, b'history one'), (second, b'history two')], {
        '/work/notes.txt': {b'history one', b'history two', expected_edit},
        '/work/unrelated.txt': {b'new round'},
    })
    assert not (current.work.parent / 'migration-pending.json').exists()


def test_changed_mapping_keeps_an_existing_workspace_version_copy(tmp_path):
    current, history, edited, first, second = edited_recovery(tmp_path)
    context.prepare(current, history, [], lambda _: pytest.fail())
    # A still-available recovery copy must remain indexed when its working
    # mapping is subsequently edited; only truly unavailable hashes disappear.
    item = next(item for item in index(current)['files'] if item['sources'] == ['workspace'])
    retained = write(current.work, '.context-recovered/workspace/'
                     + item['sourceChecksum'] + '/notes.txt', b'edited recovery')
    edited.write_bytes(b'edited again')
    add_rollback(current, history, 'unrelated.txt', b'new round')
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'edited again'
    assert retained.read_bytes() == b'edited recovery'
    assert_versions(current, [(first, b'history one'), (second, b'history two')], {
        '/work/notes.txt': {b'history one', b'history two', b'edited recovery', b'edited again'},
        '/work/unrelated.txt': {b'new round'},
    })


@pytest.mark.parametrize('failure', [None, 'context-index.json', 'manifest.json'])
def test_ordinary_edit_keeps_working_path_during_normal_continuation(
        tmp_path, monkeypatch, failure):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'history')
    current = workspace(tmp_path, old.home.parent.name)
    history = [row(old)]
    context.prepare(current, history, [], lambda _: pytest.fail())
    edited = write(current.work, 'notes.txt', b'current edit')
    save = fs.save
    if failure:
        def fail_metadata(path, data):
            if path.name == failure:
                raise OSError('interrupted metadata')
            return save(path, data)
        monkeypatch.setattr(fs, 'save', fail_metadata)
        with pytest.raises(OSError, match='interrupted metadata'):
            context.prepare(current, history, [], lambda _: pytest.fail())
        monkeypatch.setattr(fs, 'save', save)
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'current edit'
    assert restored(current) == {'/work/notes.txt': {b'history', b'current edit'}}
    add_rollback(current, history, 'unrelated.txt', b'new round')
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert edited.read_bytes() == b'current edit'
    assert_versions(current, [(old, b'history')], {
        '/work/notes.txt': {b'history', b'current edit'}, '/work/unrelated.txt': {b'new round'},
    })
    add_rollback(current, history, 'notes.txt', b'competing legacy')
    context.prepare(current, history, [], lambda _: pytest.fail())
    assert not edited.exists()
    assert restored(current) == {
        '/work/notes.txt': {b'history', b'current edit', b'competing legacy'},
        '/work/unrelated.txt': {b'new round'},
    }
