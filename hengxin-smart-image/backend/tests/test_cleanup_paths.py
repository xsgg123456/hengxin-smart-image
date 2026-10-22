"""Shared deletion contract: conservative boundaries, scope and failure semantics."""
import os
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.execution import cleanup_paths as paths


def workspace(tmp_path):
    identifier = uuid4()
    target = tmp_path / str(identifier)
    home = target / 'home/.codex'
    for part in ('cache', 'plugins', 'sessions'):
        (home / part).mkdir(parents=True)
        (home / part / 'data').write_bytes(b'private')
    return identifier, target, home


@pytest.mark.parametrize('cache_only', [False, True])
def test_missing_uuid_and_missing_root_are_idempotent(tmp_path, cache_only):
    paths.clean(tmp_path, uuid4(), cache_only)
    paths.clean(tmp_path / 'absent', uuid4(), cache_only)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('cache_only', [False, True])
def test_hardlinks_are_rejected_without_removing_either_file(tmp_path, cache_only):
    identifier, target, home = workspace(tmp_path)
    external = tmp_path / 'shared-auth'
    external.write_bytes(b'secret sentinel')
    hardlink = (home / 'plugins' if cache_only else target) / 'shared'
    os.link(external, hardlink)
    with pytest.raises(paths.CleanupSafetyError, match='NON_PRIVATE_MATERIAL'):
        paths.clean(tmp_path, identifier, cache_only)
    assert external.read_bytes() == hardlink.read_bytes() == b'secret sentinel'
    assert (home / 'cache/data').read_bytes() == b'private'


def test_both_caches_are_preflighted_before_first_removal(tmp_path):
    identifier, _, home = workspace(tmp_path)
    (home / 'plugins/data').unlink()
    (home / 'plugins').rmdir()
    (home / 'plugins').write_bytes(b'not a directory')
    with pytest.raises(paths.CleanupSafetyError, match='ROOT_INVALID'):
        paths.clean(tmp_path, identifier, True)
    assert (home / 'cache/data').read_bytes() == b'private'
    assert (home / 'plugins').read_bytes() == b'not a directory'


@pytest.mark.parametrize('location', ['root', 'target', 'home', 'codex'])
def test_non_directory_ancestors_are_rejected(tmp_path, location):
    identifier = uuid4()
    target = tmp_path / str(identifier)
    root = tmp_path
    if location == 'root':
        root = tmp_path / 'file'
        entry = root
    else:
        entry = target
        if location in ('home', 'codex'):
            entry /= 'home'
        if location == 'codex':
            entry /= '.codex'
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_bytes(b'must remain')
    with pytest.raises(paths.CleanupSafetyError, match='ROOT_INVALID'):
        paths.clean(root, identifier, True)
    assert entry.read_bytes() == b'must remain'


@pytest.mark.parametrize('cache_only', [False, True])
def test_permission_error_never_claims_success(tmp_path, monkeypatch, cache_only):
    identifier, target, home = workspace(tmp_path)

    def denied(*args, **kwargs):
        raise PermissionError('private details must not become safety error messages')

    if os.name == 'posix':
        monkeypatch.setattr(paths, '_remove_tree', denied)
    else:
        monkeypatch.setattr(paths.shutil, 'rmtree', denied)
    with pytest.raises(PermissionError):
        paths.clean(tmp_path, identifier, cache_only)
    assert target.is_dir() and (home / 'cache/data').read_bytes() == b'private'


@pytest.mark.parametrize('cache_only', [False, True])
def test_silent_incomplete_removal_is_an_error(tmp_path, monkeypatch, cache_only):
    identifier, target, _ = workspace(tmp_path)
    def noop(*args, **kwargs):
        pass
    if os.name == 'posix':
        monkeypatch.setattr(paths, '_remove_tree', noop)
    else:
        monkeypatch.setattr(paths.shutil, 'rmtree', noop)
    with pytest.raises(paths.CleanupSafetyError, match='UNSAFE_REMOVAL'):
        paths.clean(tmp_path, identifier, cache_only)
    assert target.is_dir()


@pytest.mark.skipif(os.name != 'posix', reason='Linux real links and descriptor traversal')
@pytest.mark.parametrize('location', ['home', 'codex', 'cache_tool', 'plugins_tool'])
def test_cache_never_follows_ancestor_or_fake_tool_links(tmp_path, location):
    identifier, target, home = workspace(tmp_path)
    external = tmp_path / 'outside'
    external.mkdir()
    sentinel = external / 'secret'
    sentinel.write_bytes(b'external')
    if location in ('home', 'codex'):
        original = target / 'home' if location == 'home' else home
        original.rename(original.with_name('saved'))
        original.symlink_to(external, target_is_directory=True)
    else:
        fake = home / ('cache' if location == 'cache_tool' else 'plugins') / 'home/.codex/tmp/arg0/codex-arg0Safe42'
        fake.mkdir(parents=True)
        (fake / 'apply_patch').symlink_to('/opt/codex')
    with pytest.raises(paths.CleanupSafetyError, match='UNEXPECTED_LINK'):
        paths.clean(tmp_path, identifier, True)
    assert sentinel.read_bytes() == b'external'
    if location.endswith('_tool'):
        assert (home / 'cache/data').read_bytes() == b'private'
        assert (home / 'plugins/data').read_bytes() == b'private'


@pytest.mark.skipif(os.name != 'posix', reason='Linux descriptor identity checks')
@pytest.mark.parametrize('cache_only', [False, True])
def test_replaced_target_is_rejected_before_deletion(tmp_path, monkeypatch, cache_only):
    identifier, target, home = workspace(tmp_path)
    original = paths.inspect_fd
    replaced = home / 'cache' if cache_only else target
    saved = tmp_path / 'saved'
    external = tmp_path / 'outside'
    external.mkdir()
    sentinel = external / 'secret'
    sentinel.write_bytes(b'external')
    changed = False

    def replace_after_inspection(*args, **kwargs):
        nonlocal changed
        original(*args, **kwargs)
        if not changed:
            changed = True
            replaced.rename(saved)
            replaced.symlink_to(external, target_is_directory=True)

    monkeypatch.setattr(paths, 'inspect_fd', replace_after_inspection)
    with pytest.raises(paths.CleanupSafetyError, match='TARGET_CHANGED'):
        paths.clean(tmp_path, identifier, cache_only)
    assert sentinel.read_bytes() == b'external'
    assert saved.is_dir() and replaced.is_symlink()


@pytest.mark.skipif(os.name != 'posix', reason='Linux safe descriptor availability')
def test_missing_nofollow_support_is_rejected(tmp_path, monkeypatch):
    identifier, target, _ = workspace(tmp_path)
    monkeypatch.delattr(paths.os, 'O_NOFOLLOW')
    with pytest.raises(paths.CleanupSafetyError, match='UNSAFE_REMOVAL'):
        paths.clean(tmp_path, identifier)
    assert target.exists()


@pytest.mark.skipif(os.name != 'posix', reason='Linux descriptor mount boundaries')
@pytest.mark.parametrize('location', ['target', 'cache', 'nested'])
def test_cross_device_boundary_is_rejected(tmp_path, monkeypatch, location):
    identifier, target, home = workspace(tmp_path)
    boundary = target if location == 'target' else home / 'cache'
    if location == 'nested':
        boundary = home / 'cache/nested'
        boundary.mkdir()
    original = paths._directory

    def different_device(info, device=None):
        if info.st_ino == boundary.stat().st_ino and device is not None:
            info = SimpleNamespace(st_mode=info.st_mode, st_dev=device + 1)
        return original(info, device)

    monkeypatch.setattr(paths, '_directory', different_device)
    with pytest.raises(paths.CleanupSafetyError, match='CROSS_DEVICE'):
        paths.clean(tmp_path, identifier, location != 'target')
    assert (home / 'cache/data').read_bytes() == b'private'


def test_error_classification_does_not_echo_arbitrary_text():
    error = paths.CleanupSafetyError('secret/auth/private/prompt')
    assert error.code == str(error) == 'UNSAFE_REMOVAL'


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows junction boundary')
@pytest.mark.parametrize('location', ['root', 'task', 'cache'])
def test_windows_junction_is_rejected_without_touching_external(tmp_path, location):
    identifier = uuid4()
    root = tmp_path / 'root'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'auth.json'
    sentinel.write_bytes(b'external credential')
    if location == 'root':
        junction = tmp_path / 'alias'
        root = junction
    elif location == 'task':
        junction = root / str(identifier)
    else:
        junction = root / str(identifier) / 'home/.codex/cache'
        junction.parent.mkdir(parents=True)
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(paths.CleanupSafetyError, match='UNEXPECTED_LINK'):
            paths.clean(root, identifier, location == 'cache')
        assert sentinel.read_bytes() == b'external credential'
    finally:
        junction.rmdir()  # Remove only the junction itself, never its target tree.
