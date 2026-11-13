"""Captured output bytes remain fixed when work files change later."""
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import tracemalloc
from uuid import uuid4

import pytest

from app.modules.domestic_studio.delivery_capture import capture
from files_helpers import image_bytes
from test_studio_skill_cache import new_workspace


def test_explicit_file_is_snapshotted_once_and_recovered_without_model(tmp_path):
    workspace = new_workspace(tmp_path)
    source = workspace.work / 'final.png'
    original = image_bytes()
    source.write_bytes(original)
    summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1',
                              final_text='![成品](/work/final.png)')
    identity = {key: str(uuid4()) for key in ('jobId', 'taskId', 'turnId', 'conversationId')}
    manifest, images, issues = capture(workspace, summary, identity)
    images = list(images)
    assert manifest['ready'] and len(images) == 1 and not issues
    assert images[0][1].path.read_bytes() == original
    source.write_bytes(b'changed after capture')
    recovered, images, issues = capture(workspace, summary, identity)
    images = list(images)
    assert recovered == manifest and images[0][1].path.read_bytes() == original and not issues
    with pytest.raises(ValueError, match='identity|reply'):
        capture(workspace, SimpleNamespace(**(vars(summary) | {'final_text': 'different'})), identity)


def test_incomplete_response_cannot_become_a_delivery(tmp_path):
    workspace = new_workspace(tmp_path)
    summary = SimpleNamespace(turn_completed=False, error=None, session_id='session-1', final_text='未完成')
    with pytest.raises(ValueError, match='verified'):
        capture(workspace, summary, {})
    assert not (workspace.control / 'delivery').exists()


def test_damaged_snapshot_does_not_hide_other_frozen_or_original_files(tmp_path):
    workspace = new_workspace(tmp_path)
    (workspace.work / 'one.png').write_bytes(image_bytes())
    (workspace.work / 'two.png').write_bytes(image_bytes())
    summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1',
                              final_text='![一](/work/one.png) ![二](/work/two.png)')
    identity = {key: str(uuid4()) for key in ('jobId', 'taskId', 'turnId', 'conversationId')}
    manifest, files, issues = capture(workspace, summary, identity)
    files = list(files)
    assert manifest['ready'] and len(files) == 2 and not issues
    (workspace.control / 'delivery' / manifest['items'][0]['snapshot']).write_bytes(b'corrupt')
    _, files, issues = capture(workspace, summary, identity)
    files = list(files)
    assert len(files) == 1 and files[0][0] == '/work/two.png'
    assert issues and (workspace.work / 'one.png').read_bytes() == image_bytes()


def test_frozen_files_are_loaded_one_at_a_time(tmp_path, monkeypatch):
    from app.modules.domestic_studio import delivery_capture
    workspace = new_workspace(tmp_path)
    for name in ('one.png', 'two.png'):
        (workspace.work / name).write_bytes(image_bytes())
    summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1',
                              final_text='![一](/work/one.png) ![二](/work/two.png)')
    identity = {key: str(uuid4()) for key in ('jobId', 'taskId', 'turnId', 'conversationId')}
    _, initial, _ = capture(workspace, summary, identity)
    assert len(list(initial)) == 2
    calls = []
    original = delivery_capture.verify_file
    def verify_file(root, item):
        calls.append(item['target'])
        return original(root, item)
    monkeypatch.setattr(delivery_capture, 'verify_file', verify_file)
    _, files, _ = capture(workspace, summary, identity)
    assert calls == []
    assert next(files)[0] == '/work/one.png' and calls == ['/work/one.png']
    assert next(files)[0] == '/work/two.png' and calls == ['/work/one.png', '/work/two.png']


def test_large_generated_file_is_frozen_and_reopened_with_bounded_memory(tmp_path):
    with TemporaryDirectory(dir=tmp_path) as root:
        workspace = new_workspace(Path(root))
        source, size = workspace.work / 'large.bin', 64 * 1024 * 1024
        with source.open('wb') as handle:
            handle.truncate(size)
        summary = SimpleNamespace(turn_completed=True, error=None, session_id='session-1',
                                  final_text='[结果](/work/large.bin)')
        identity = {key: str(uuid4()) for key in ('jobId', 'taskId', 'turnId', 'conversationId')}
        tracemalloc.start()
        try:
            manifest, files, issues = capture(workspace, summary, identity)
            files = list(files)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert manifest['ready'] and len(files) == 1 and not issues
        assert files[0][1].size_bytes == size and files[0][1].path.stat().st_size == size
        assert peak < 16 * 1024 * 1024
