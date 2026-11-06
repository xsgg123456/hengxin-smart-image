"""Failure, tamper and concurrency tests; all stores are offline fakes."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.overseas.execution import skill_cache
from test_studio_skill_cache import fingerprint, new_workspace, prepare, source  # noqa: F401


@pytest.mark.parametrize('damage', ['changed', 'missing', 'extra_file', 'extra_dir', 'version_sibling'])
def test_corrupt_cache_fails_without_repair_or_download(tmp_path, source, damage):
    first = new_workspace(tmp_path)
    root = prepare(first, source.skill())
    if damage == 'changed':
        (root / 'SKILL.md').write_bytes(b'changed bytes')
    elif damage == 'missing':
        (root / 'SKILL.md').unlink()
    elif damage == 'extra_file':
        (root / 'unexpected').write_bytes(b'extra')
    elif damage == 'extra_dir':
        (root / 'unexpected').mkdir()
    else:
        (root.parent / 'unexpected').mkdir()
    before = fingerprint(root.parent)
    source.store.open.side_effect = AssertionError('Cache hit must never download')
    current = new_workspace(tmp_path, first.home.parent.name)
    with pytest.raises(ValueError):
        prepare(current, source.skill())
    assert fingerprint(root.parent) == before
    assert not (current.control / 'skill-ref.json').exists()
    assert current.local_skill is None


@pytest.mark.parametrize('link', ['symlink_file', 'symlink_dir', 'hardlink'])
def test_links_cannot_escape_cache(tmp_path, source, link):
    first = new_workspace(tmp_path)
    root = prepare(first, source.skill())
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'SKILL.md'
    sentinel.write_bytes(b'untouched outside')
    target = root / 'SKILL.md'
    if link == 'symlink_dir':
        target = root / 'escaped'
    else:
        target.unlink()
    try:
        if link == 'hardlink':
            os.link(sentinel, target)
        else:
            target.symlink_to(outside if link == 'symlink_dir' else sentinel,
                              target_is_directory=link == 'symlink_dir')
    except OSError as error:
        if os.name == 'nt' and getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows symlink privilege unavailable; mandatory Linux release test')
        raise
    current = new_workspace(tmp_path, first.home.parent.name)
    with pytest.raises(ValueError, match='link'):
        prepare(current, source.skill())
    assert sentinel.read_bytes() == b'untouched outside'


@pytest.mark.parametrize('relative', ['../escape', '/absolute', 'scripts/../../escape', 'x\\escape'])
def test_unsafe_frozen_paths_cannot_write_outside_cache(tmp_path, source, relative):
    workspace = new_workspace(tmp_path)
    with pytest.raises(ValueError):
        prepare(workspace, source.skill(files={'SKILL.md': 'valid', relative: 'escape'}))
    assert not (workspace.home.parent / 'skill-cache').exists()
    assert not (tmp_path / 'escape').exists()


def test_concurrent_first_preparation_publishes_one_complete_version(tmp_path, source):
    first = new_workspace(tmp_path)
    second = new_workspace(tmp_path, first.home.parent.name)
    skills = [source.skill(), source.skill()]
    gate = Barrier(2)

    def run(workspace, skill):
        gate.wait(timeout=10)
        return prepare(workspace, skill)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, workspace, skill)
                   for workspace, skill in zip((first, second), skills)]
        roots = [future.result(timeout=30) for future in futures]
    assert roots[0] == roots[1]
    assert set(fingerprint(roots[0])) == {'SKILL.md', 'scripts/run.py', 'assets/ref.bin'}
    assert len(list(roots[0].parent.parent.iterdir())) == 1
    assert source.reads.call_count == (1 if source.kind == 'legacy' else 0)
    assert (first.control / 'skill-ref.json').read_bytes() == (second.control / 'skill-ref.json').read_bytes()


def test_partial_write_is_removed_and_next_round_can_retry(tmp_path, source, monkeypatch):
    first = new_workspace(tmp_path)
    original_write = skill_cache.fs.write
    calls = 0

    def fail_second_file(path, content):
        nonlocal calls
        if '.stage-' in str(path):
            calls += 1
            if calls == 2:
                raise OSError('injected disk write failure')
        return original_write(path, content)

    monkeypatch.setattr(skill_cache.fs, 'write', fail_second_file)
    with pytest.raises(OSError, match='injected'):
        prepare(first, source.skill())
    assert not list((first.home.parent / 'skill-cache').iterdir())
    assert first.local_skill is None
    assert not (first.control / 'skill-ref.json').exists()
    monkeypatch.setattr(skill_cache.fs, 'write', original_write)
    retried = new_workspace(tmp_path, first.home.parent.name)
    root = prepare(retried, source.skill())
    assert (root / 'SKILL.md').read_text(encoding='utf-8') == '完整技能说明'
    assert len(list(root.parent.parent.iterdir())) == 1


@pytest.mark.parametrize('source', ['legacy'], indirect=True)
def test_legacy_corrupt_download_is_closed_and_can_retry(tmp_path, source):
    import io
    from unittest.mock import Mock
    workspace = new_workspace(tmp_path)
    skill = source.skill()
    original_open = source.store.open.side_effect
    stream = io.BytesIO(b'wrong bytes')
    stream.release_conn = Mock()
    source.store.open.side_effect = lambda asset: stream
    with pytest.raises(ValueError, match='integrity'):
        prepare(workspace, skill)
    assert stream.closed
    stream.release_conn.assert_called_once()
    assert not list((workspace.home.parent / 'skill-cache').iterdir())
    source.store.open.side_effect = original_open
    assert (prepare(workspace, skill) / 'assets/ref.bin').read_bytes() == b'\x00\xffreference'


@pytest.mark.skipif(os.name != 'posix', reason='POSIX permission bits enforced only on Linux')
def test_changed_execution_permissions_reject_hit(tmp_path, source):
    first = new_workspace(tmp_path)
    root = prepare(first, source.skill())
    (root / 'scripts/run.py').chmod(0o644)
    current = new_workspace(tmp_path, first.home.parent.name)
    with pytest.raises(ValueError, match='permissions'):
        prepare(current, source.skill())


def test_foreign_conversation_control_cannot_own_cache(tmp_path, source):
    first, second = new_workspace(tmp_path), new_workspace(tmp_path)
    first.control = second.control
    with pytest.raises(ValueError, match='belong'):
        prepare(first, source.skill())
    assert not (first.home.parent / 'skill-cache').exists()
    assert not (second.home.parent / 'skill-cache').exists()


def test_existing_cleanup_erases_private_cache_without_crossing_conversations(tmp_path, source, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.overseas.tasks import cleanup_files
    first, second = new_workspace(tmp_path / 'studio'), new_workspace(tmp_path / 'studio')
    deleted, retained = prepare(first, source.skill()), prepare(second, source.skill())
    before = fingerprint(retained)
    monkeypatch.setattr(cleanup_files, 'get_settings',
                        lambda: SimpleNamespace(codex_execution_root=str(tmp_path)))
    store = Mock()
    cleanup_files.erase(store, dict(root=str(tmp_path), objects=[],
                                   directories=['studio/' + first.home.parent.name]))
    assert not deleted.exists() and not first.home.parent.exists()
    assert fingerprint(retained) == before
    store.remove.assert_not_called()
