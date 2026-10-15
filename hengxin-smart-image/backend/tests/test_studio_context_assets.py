"""Persistent original inputs use only trusted frozen metadata and bytes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.overseas.studio import context_workspace as context


def asset(content=b'original', name='original.pdf', identity=None, object_key=None):
    identity = str(identity or uuid4())
    return dict(id=identity, name=name, bucket='test-only', object_key=object_key or identity,
                content_type='application/octet-stream', size_bytes=len(content),
                checksum=hashlib.sha256(content).hexdigest())


def workspace(tmp_path, conversation=None, turn=None):
    root = tmp_path / str(conversation or uuid4())
    result = SimpleNamespace(home=root / 'home', work=root / 'rounds' / str(turn or uuid4()),
                             control=root / 'control' / str(uuid4()))
    for path in (result.home, result.work, result.control):
        path.mkdir(parents=True, exist_ok=True)
    return result


def original_path(ws, item):
    return ws.inputs_root / item['path'].removeprefix('/work/inputs/')


def test_three_rounds_keep_original_and_editable_work_without_redownload(tmp_path):
    first = workspace(tmp_path)
    content, calls = b'first original', []
    item = asset(content)
    def read(source):
        calls.append(source['id'])
        return content
    paths = context.prepare(first, [], [item], read)
    (first.work / 'notes.txt').write_text('remember this')
    original = original_path(first, paths[0])
    history = [dict(turn_id=first.round_work.name, inputs=[item])]
    for _ in range(2):
        next_round = workspace(tmp_path, first.home.parent.name)
        assert context.prepare(next_round, history, [], read) == []
        assert next_round.home == first.home and next_round.work == first.work
        assert next_round.round_work != first.round_work
        assert original.read_bytes() == content
        assert (next_round.work / 'notes.txt').read_text() == 'remember this'
        assert not next_round.recovery_notice
        history.append(dict(turn_id=next_round.round_work.name, inputs=[]))
    assert len(calls) == 1


def test_same_names_and_new_resource_version_never_overwrite(tmp_path):
    ws = workspace(tmp_path)
    first = asset(b'first', '同名.pptx')
    second = asset(b'second', '同名.pptx')
    changed = asset(b'changed', '同名.pptx', first['id'], first['object_key'])
    data = {row['checksum']: value for row, value in [(first, b'first'), (second, b'second'), (changed, b'changed')]}
    paths = context.prepare(ws, [], [first, second, changed], lambda row: data[row['checksum']])
    assert len({row['path'] for row in paths}) == 3
    assert [original_path(ws, row).read_bytes() for row in paths] == [b'first', b'second', b'changed']
    visible = json.loads(ws.context_index.read_text())
    assert 'bucket' not in json.dumps(visible) and 'object_key' not in json.dumps(visible)


@pytest.mark.parametrize('damage', ['deleted', 'changed'])
def test_missing_and_tampered_registered_inputs_restore_from_frozen_source(tmp_path, damage):
    ws = workspace(tmp_path)
    item = asset()
    paths = context.prepare(ws, [], [item], lambda _: b'original')
    target = original_path(ws, paths[0])
    target.unlink() if damage == 'deleted' else target.write_bytes(b'changed!')
    next_round = workspace(tmp_path, ws.home.parent.name)
    calls = []
    def read(row):
        calls.append(row)
        return b'original'
    context.prepare(next_round, [dict(turn_id=ws.round_work.name, inputs=[item])], [], read)
    assert target.read_bytes() == b'original' and len(calls) == 1
    assert next_round.recovery_notice


def test_failed_store_or_checksum_does_not_commit_initial_layout(tmp_path):
    ws = workspace(tmp_path)
    with pytest.raises(ValueError, match='恢复校验'):
        context.prepare(ws, [], [asset()], lambda _: b'wrong')
    assert not (ws.home.parent / 'persistent').exists()
    assert list(ws.home.parent.glob('.context-stage-*')) == []
    context.prepare(ws, [], [asset()], lambda _: b'original')
    assert ws.persistent


def test_new_conversation_has_no_old_inputs_or_work(tmp_path):
    first = workspace(tmp_path)
    context.prepare(first, [], [asset()], lambda _: b'original')
    (first.work / 'notes').write_text('private')
    second = workspace(tmp_path)
    context.prepare(second, [], [], lambda _: pytest.fail('unexpected source read'))
    assert list(second.inputs_root.iterdir()) == []
    assert not (second.work / 'notes').exists()


def test_filename_path_traversal_is_normalized_only_into_a_versioned_leaf(tmp_path):
    ws = workspace(tmp_path)
    paths = context.prepare(ws, [], [asset(name='../../evil.pdf')], lambda _: b'original')
    assert original_path(ws, paths[0]).is_relative_to(ws.inputs_root)
    assert original_path(ws, paths[0]).name == '_.._evil.pdf'
