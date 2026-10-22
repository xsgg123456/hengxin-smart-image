"""Same-device bind mounts must not expose external files to workspace cleanup."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from app.execution import cleanup_paths as paths
from test_cleanup_paths import workspace


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux kernel mount identity')
@pytest.mark.parametrize('evidence', ['missing', 'malformed'])
def test_missing_mount_identity_fails_closed(tmp_path, monkeypatch, evidence):
    identifier, target, home = workspace(tmp_path)
    original = Path.read_text

    def unavailable(path, *args, **kwargs):
        if str(path).startswith('/proc/self/fdinfo/'):
            if evidence == 'missing':
                raise PermissionError('kernel evidence unavailable')
            return 'mnt_id: invalid\n'
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', unavailable)
    with pytest.raises(paths.CleanupSafetyError, match='UNSAFE_REMOVAL'):
        paths.clean(tmp_path, identifier)
    assert target.exists() and (home / 'cache/data').read_bytes() == b'private'


SCRIPT = r'''
import subprocess, sys
from pathlib import Path
from uuid import uuid4
from app.execution.cleanup_paths import clean, CleanupSafetyError
base, location = Path(sys.argv[1]), sys.argv[2]
external = base / 'outside'
external.mkdir()
sentinel = external / 'must-survive'
sentinel.write_bytes(b'external same-device sentinel')
root, identifier = base / 'execution', uuid4()
target = root / str(identifier)
suffix = {'target': '', 'home': 'home', 'cache': 'home/.codex/cache',
          'plugins': 'home/.codex/plugins', 'nested': 'home/.codex/cache/nested',
          'history_nested': 'home/.codex/sessions/nested', 'file': 'mounted-file',
          'cache_file': 'home/.codex/cache/mounted-file'}[location]
mountpoint = target / suffix
if location in ('file', 'cache_file'):
    mountpoint.parent.mkdir(parents=True)
    mountpoint.write_bytes(b'private')
else:
    mountpoint.mkdir(parents=True)
source = sentinel if location in ('file', 'cache_file') else external
subprocess.run(['mount', '--bind', str(source), str(mountpoint)], check=True)
try:
    assert root.stat().st_dev == mountpoint.stat().st_dev
    try:
        clean(root, identifier, cache_only=location not in ('target', 'history_nested', 'file'))
    except CleanupSafetyError as error:
        assert error.code == 'CROSS_DEVICE', error.code
    else:
        raise AssertionError('same-device mount was accepted')
    assert sentinel.read_bytes() == b'external same-device sentinel'
finally:
    subprocess.run(['umount', str(mountpoint)], check=True)
'''


@pytest.fixture
def mount_namespace():
    if sys.platform != 'linux' or os.geteuid() != 0:
        pytest.skip('Linux root with isolated mount namespace required')
    if not all(shutil.which(name) for name in ('unshare', 'mount', 'umount')):
        pytest.skip('Linux mount tools unavailable')
    probe = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--', 'true'],
                           capture_output=True)
    if probe.returncode:
        pytest.skip('Isolated mount namespace capability unavailable')


@pytest.mark.parametrize('location', ['target', 'home', 'cache', 'plugins', 'nested',
                                      'history_nested', 'file', 'cache_file'])
def test_real_same_device_bind_mount_is_refused(tmp_path, mount_namespace, location):
    result = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--',
                             sys.executable, '-c', SCRIPT, str(tmp_path), location],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('cache_only', [False, True])
def test_same_inode_mount_replacement_after_preflight_is_refused(tmp_path, mount_namespace, cache_only):
    script = r'''
import os, subprocess, sys
from pathlib import Path
from app.execution import cleanup_paths as paths
from uuid import uuid4
root, identifier = Path(sys.argv[1]), uuid4()
target = root / str(identifier)
cache_only = sys.argv[2] == 'True'
boundary = target / 'home/.codex/cache' if cache_only else target
boundary.mkdir(parents=True)
sentinel = boundary / 'must-survive'
sentinel.write_bytes(b'private unchanged')
original, mounted = paths.inspect_fd, False
def mount_after_preflight(fd, *args, **kwargs):
    global mounted
    original(fd, *args, **kwargs)
    if not mounted and os.fstat(fd).st_ino == boundary.stat().st_ino:
        subprocess.run(['mount', '--bind', str(boundary), str(boundary)], check=True)
        mounted = True
paths.inspect_fd = mount_after_preflight
try:
    try:
        paths.clean(root, identifier, cache_only)
    except paths.CleanupSafetyError as error:
        assert error.code == 'TARGET_CHANGED', error.code
    else:
        raise AssertionError('replacement mount was accepted')
    assert mounted and sentinel.read_bytes() == b'private unchanged'
finally:
    if mounted:
        subprocess.run(['umount', str(boundary)], check=True)
'''
    result = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--',
                             sys.executable, '-c', script, str(tmp_path), str(cache_only)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('cache_only', [False, True])
def test_nested_bind_added_after_preflight_never_erases_external_files(tmp_path, mount_namespace, cache_only):
    script = r'''
import subprocess, sys
from pathlib import Path
from uuid import uuid4
from app.execution import cleanup_paths as paths
root, identifier = Path(sys.argv[1]), uuid4()
target = root / str(identifier)
cache_only = sys.argv[2] == 'True'
boundary = target / 'home/.codex/cache' if cache_only else target
nested = boundary / 'nested'
nested.mkdir(parents=True)
external = root / 'outside'
external.mkdir()
sentinel = external / 'must-survive'
sentinel.write_bytes(b'external raced bind sentinel')
original, mounted = paths.inspect_fd, False
def inject(*args, **kwargs):
    global mounted
    original(*args, **kwargs)
    if not mounted:
        subprocess.run(['mount', '--bind', str(external), str(nested)], check=True)
        mounted = True
paths.inspect_fd = inject
try:
    try:
        paths.clean(root, identifier, cache_only)
    except paths.CleanupSafetyError as error:
        assert error.code == 'CROSS_DEVICE', error.code
    else:
        raise AssertionError('raced mount was accepted')
    assert mounted and sentinel.read_bytes() == b'external raced bind sentinel'
finally:
    if mounted:
        subprocess.run(['umount', str(nested)], check=True)
'''
    result = subprocess.run(['unshare', '--mount', '--propagation', 'private', '--',
                             sys.executable, '-c', script, str(tmp_path), str(cache_only)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
