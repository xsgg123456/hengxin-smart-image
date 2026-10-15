"""Legacy sources survive successful, conflicting and interrupted migrations."""
import json

import pytest

from app.overseas.studio import context_fs as fs
from app.overseas.studio import context_workspace as context
from test_studio_context_assets import asset, workspace


def write(root, name, content):
    target = fs.checked(root / name, missing=True)
    fs.mkdir(target.parent)
    target.write_bytes(content)
    return target


def row(ws, inputs=()):
    return dict(turn_id=ws.work.name, inputs=list(inputs))


def index(ws):
    return json.loads(ws.context_index.read_text(encoding='utf-8'))


def test_real_legacy_shapes_restore_original_aliases_and_research_without_download(tmp_path):
    old = workspace(tmp_path)
    one, two = asset(b'presentation', 'brief.pptx'), asset(b'table', 'details.xlsx')
    write(old.work, 'inputs/1.pptx', b'presentation')
    write(old.work, 'inputs/2.xlsx', b'table')
    write(old.work, 'zzz13/research/ppt_images.json', b'["image-1"]')
    write(old.work, 'zzz13/research/1.png', b'image bytes')
    write(old.work, 'extract.py', b'print("extract")')
    write(old.work, 'input.json', b'{"forged frozen source":true}')
    write(old.work, 'skills/old/SKILL.md', b'must not persist')
    write(old.work, '.codex/private', b'not a working file')
    write(old.work, '.context-files.json', b'forged index')
    next_round = workspace(tmp_path, old.home.parent.name)
    history = [row(old, [one, two])]
    before = context.inspect(next_round, history)
    assert before['ordinaryFiles'] == 3 and before['inputFiles'] == 2
    assert not (old.home.parent / '.context-prepare.lock').exists()
    context.prepare(next_round, history, [], lambda _: pytest.fail('old originals are valid'))
    assert (next_round.inputs_root / '1.pptx').read_bytes() == b'presentation'
    assert (next_round.inputs_root / '2.xlsx').read_bytes() == b'table'
    assert (next_round.work / 'zzz13/research/ppt_images.json').read_bytes() == b'["image-1"]'
    assert (next_round.work / 'extract.py').read_bytes() == b'print("extract")'
    assert not (next_round.work / 'skills/old').exists()
    assert not (next_round.work / '.codex').exists()
    assert (old.work / 'inputs/1.pptx').read_bytes() == b'presentation'
    assert next_round.recovery_notice
    assert context.inspect(next_round, history)['digest'] == before['digest']
    context.prepare(next_round, history, [], lambda _: pytest.fail('must reuse valid original'))
    assert next_round.recovery_notice  # Preparation alone has not dispatched its prompt.
    later = workspace(tmp_path, old.home.parent.name)
    context.prepare(later, [*history, dict(turn_id=next_round.round_work.name, inputs=[])], [], lambda _: pytest.fail())
    assert not later.recovery_notice


def test_conflicting_ordinary_and_input_paths_have_all_versions_and_no_ambiguous_alias(tmp_path):
    first = workspace(tmp_path)
    second = workspace(tmp_path, first.home.parent.name)
    a, b = asset(b'first', 'first.pdf'), asset(b'second', 'second.pdf')
    write(first.work, 'inputs/1.pdf', b'first')
    write(second.work, 'inputs/1.pdf', b'second')
    write(first.work, 'notes.txt', b'old notes')
    write(second.work, 'notes.txt', b'new notes')
    current = workspace(tmp_path, first.home.parent.name)
    context.prepare(current, [row(first, [a]), row(second, [b])], [], lambda _: pytest.fail())
    assert not (current.inputs_root / '1.pdf').exists()
    assert not (current.work / 'notes.txt').exists()
    entries = index(current)['files']
    assert all(item['conflict'] for item in entries)
    assert {fs.checked(current.work / item['path'].removeprefix('/work/')).read_bytes()
            for item in entries} == {b'old notes', b'new notes'}
    assert any(item['conflict'] for item in index(current)['inputs'])


def test_legacy_file_directory_collision_preserves_both_versions(tmp_path):
    first = workspace(tmp_path)
    second = workspace(tmp_path, first.home.parent.name)
    write(first.work, 'result', b'file')
    write(second.work, 'result/design.png', b'image')
    current = workspace(tmp_path, first.home.parent.name)
    context.prepare(current, [row(first), row(second)], [], lambda _: pytest.fail())
    assert not (current.work / 'result').exists()
    assert len(index(current)['files']) == 2
    assert all(item['conflict'] for item in index(current)['files'])


def test_changed_legacy_source_and_rollback_new_turn_reinventory_safely(tmp_path):
    first = workspace(tmp_path)
    write(first.work, 'notes.txt', b'one')
    current = workspace(tmp_path, first.home.parent.name)
    first_history = [row(first)]
    before = context.inspect(current, first_history)
    context.prepare(current, first_history, [], lambda _: pytest.fail())
    (first.work / 'notes.txt').write_bytes(b'two')
    assert context.inspect(current, first_history)['digest'] != before['digest']
    context.prepare(current, first_history, [], lambda _: pytest.fail())
    assert not (current.work / 'notes.txt').exists()
    assert len(index(current)['files']) == 2
    rollback_turn = workspace(tmp_path, first.home.parent.name)
    write(rollback_turn.work, 'new-script.py', b'new legacy file after rollback')
    context.prepare(current, [*first_history, row(rollback_turn)], [], lambda _: pytest.fail())
    assert (current.work / 'new-script.py').read_bytes() == b'new legacy file after rollback'
    assert len(index(current)['files']) == 3


def test_incremental_conflict_preserves_current_user_edit(tmp_path):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'old')
    current = workspace(tmp_path, old.home.parent.name)
    context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    (current.work / 'notes.txt').write_bytes(b'edited by user')
    other = workspace(tmp_path, old.home.parent.name)
    write(other.work, 'notes.txt', b'new legacy')
    context.prepare(current, [row(old), row(other)], [], lambda _: pytest.fail())
    data = {fs.checked(current.work / item['path'].removeprefix('/work/')).read_bytes()
            for item in index(current)['files']}
    assert data == {b'old', b'edited by user', b'new legacy'}
    assert not (current.work / 'notes.txt').exists()


def test_copy_failure_is_retryable_and_never_mutates_old_round(tmp_path, monkeypatch):
    old = workspace(tmp_path)
    write(old.work, 'one.txt', b'one')
    write(old.work, 'two.txt', b'two')
    current = workspace(tmp_path, old.home.parent.name)
    original, count = fs.copy, 0
    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated disk interruption')
        return original(*args, **kwargs)
    monkeypatch.setattr(fs, 'copy', fail_second)
    with pytest.raises(OSError, match='interruption'):
        context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    assert not (old.home.parent / 'persistent').exists()
    assert (old.work / 'one.txt').read_bytes() == b'one'
    assert (old.work / 'two.txt').read_bytes() == b'two'
    monkeypatch.setattr(fs, 'copy', original)
    context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    assert (current.work / 'two.txt').read_bytes() == b'two'


def test_restore_can_use_existing_last_turn_without_creating_a_database_turn(tmp_path):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'one')
    history = [row(old)]
    legacy_path = old.work
    context.prepare(old, history, [], lambda _: pytest.fail())
    (legacy_path / 'notes.txt').write_bytes(b'two')
    context.prepare(old, history, [], lambda _: pytest.fail())
    assert len(index(old)['files']) == 2


def test_inspect_tracks_original_source_deletion_and_db_frozen_changes_without_writes(tmp_path):
    old = workspace(tmp_path)
    item = asset()
    original = write(old.work, 'inputs/1.pdf', b'original')
    history = [row(old, [item])]
    before = context.inspect(old, history)
    original.unlink()
    assert context.inspect(old, history)['digest'] != before['digest']
    assert not (old.home.parent / 'persistent').exists()
    assert not (old.home.parent / '.context-prepare.lock').exists()


def test_user_hidden_work_files_survive_but_platform_private_directories_do_not(tmp_path):
    old = workspace(tmp_path)
    write(old.work, '.notes.txt', b'hidden notes')
    write(old.work, '.assets/research.png', b'hidden research')
    write(old.work, '.aws/credentials', b'private')
    current = workspace(tmp_path, old.home.parent.name)
    context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    assert (current.work / '.notes.txt').read_bytes() == b'hidden notes'
    assert (current.work / '.assets/research.png').read_bytes() == b'hidden research'
    assert not (current.work / '.aws').exists()


def test_metadata_failure_after_conflict_removal_retains_user_edit_in_retry_index(tmp_path, monkeypatch):
    old = workspace(tmp_path)
    write(old.work, 'notes.txt', b'original')
    current = workspace(tmp_path, old.home.parent.name)
    context.prepare(current, [row(old)], [], lambda _: pytest.fail())
    (current.work / 'notes.txt').write_bytes(b'user edit')
    other = workspace(tmp_path, old.home.parent.name)
    write(other.work, 'notes.txt', b'new historical content')
    history = [row(old), row(other)]
    save = fs.save
    def fail_index(path, data):
        if path.name == 'context-index.json':
            raise OSError('metadata disk failure')
        save(path, data)
    monkeypatch.setattr(fs, 'save', fail_index)
    with pytest.raises(OSError, match='metadata disk failure'):
        context.prepare(current, history, [], lambda _: pytest.fail())
    assert not (current.work / 'notes.txt').exists()
    monkeypatch.setattr(fs, 'save', save)
    context.prepare(current, history, [], lambda _: pytest.fail())
    restored = {fs.checked(current.work / item['path'].removeprefix('/work/')).read_bytes()
                for item in index(current)['files']}
    assert restored == {b'original', b'user edit', b'new historical content'}
    assert not (current.work.parent / 'migration-pending.json').exists()
