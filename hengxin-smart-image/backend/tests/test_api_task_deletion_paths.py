"""Real Linux descriptor, symlink and process tests; local Windows path boundary checks."""
import os
from pathlib import Path
import shutil
import subprocess
import socket
import tempfile
import sys
from uuid import uuid4
import pytest
from app.execution.process import process_identity, same_process
from app.modules.api_image_edits.deletion_paths import clean


def workspace(tmp_path):
    identifier = uuid4()
    root = tmp_path / 'execution'
    target = root / 'api-edits' / str(identifier)
    (target / 'home' / '.codex' / 'sessions').mkdir(parents=True)
    (target / 'home' / '.codex' / 'sessions' / 'private.jsonl').write_text('private')
    return root, identifier, target


def test_exact_uuid_removal_preserves_neighbors_and_public_auth(tmp_path):
    root, identifier, target = workspace(tmp_path)
    neighbor = root / 'api-edits' / str(uuid4())
    neighbor.mkdir()
    auth = tmp_path / 'auth.json'
    auth.write_text('shared auth')
    clean(root, identifier)
    assert not target.exists() and neighbor.is_dir() and auth.read_text() == 'shared auth'
    clean(root, identifier)
    with pytest.raises(ValueError): clean(root, '../escape')


@pytest.mark.skipif(os.name != 'posix', reason='Linux native executor filesystem')
@pytest.mark.parametrize('link', ['ancestor', 'workspace', 'session', 'hardlink', 'unknown_tool', 'tool_target'])
def test_external_material_is_never_followed_or_modified(tmp_path, link):
    root, identifier, target = workspace(tmp_path)
    outside = tmp_path / 'shared'
    outside.mkdir()
    sentinel = outside / 'auth.json'
    sentinel.write_text('keep')
    if link == 'ancestor':
        moved = tmp_path / 'moved'
        root.rename(moved)
        root.symlink_to(moved, target_is_directory=True)
    elif link == 'workspace':
        shutil.rmtree(target)
        target.symlink_to(outside, target_is_directory=True)
    elif link == 'session':
        (target / 'home' / 'outside').symlink_to(outside, target_is_directory=True)
    elif link == 'hardlink':
        os.link(sentinel, target / 'shared-auth.json')
    else:
        tools = target / 'home' / '.codex' / 'tmp' / 'arg0' / 'codex-arg0Safe42'
        tools.mkdir(parents=True)
        (tools / ('unsafe' if link == 'unknown_tool' else 'apply_patch')).symlink_to(
            '/opt/codex' if link == 'unknown_tool' else sentinel)
    with pytest.raises((ValueError, OSError)):
        clean(root, identifier)
    assert sentinel.read_text() == 'keep'


@pytest.mark.skipif(os.name != 'posix', reason='Linux safe rmtree support')
def test_existing_codex_sandbox_tool_links_are_unlinked_not_followed(tmp_path):
    root, identifier, target = workspace(tmp_path)
    tools = target / 'home' / '.codex' / 'tmp' / 'arg0' / 'codex-arg0Safe42'
    tools.mkdir(parents=True)
    for name in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'):
        (tools / name).symlink_to('/opt/codex')
    clean(root, identifier)
    assert not target.exists()


@pytest.mark.skipif(os.name != 'posix', reason='Native Linux session IPC endpoints')
def test_dead_session_socket_and_fifo_are_unlinked():
    # Linux sockaddr_un is limited to 108 bytes; pytest's nested path can exceed it.
    with tempfile.TemporaryDirectory(prefix='hx-ipc-', dir='/tmp') as temporary:
        root, identifier, target = workspace(Path(temporary))
        with socket.socket(socket.AF_UNIX) as channel:
            channel.bind(str(target / 'session.sock'))
        os.mkfifo(target / 'session.fifo')
        clean(root, identifier)
        assert not target.exists()


@pytest.mark.skipif(os.name != 'posix', reason='Native Linux /proc identity proof')
def test_real_process_identity_distinguishes_running_and_exited():
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
    try:
        boot, birth = process_identity(process.pid)
        assert same_process(process.pid, boot, birth)
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert not same_process(process.pid, boot, birth)


@pytest.mark.skipif(os.name != 'posix' or getattr(os, 'geteuid', lambda: -1)() != 0,
                   reason='Linux container root required to model real service UIDs')
def test_native_owner_can_erase_where_api_uid_cannot():
    # Separate OS identities, not mocked permission checks; no host/production paths.
    with tempfile.TemporaryDirectory(prefix='hx-delete-uid-', dir='/tmp') as temporary:
        shared = Path(temporary)
        shared.chmod(0o755)
        root, identifier, target = workspace(shared)
        for directory, folders, files in os.walk(root):
            os.chown(directory, 1001, 1001)
            Path(directory).chmod(0o700)
            for filename in files:
                os.chown(Path(directory) / filename, 1001, 1001)
        code = 'from app.modules.api_image_edits.deletion_paths import clean; clean(*__import__("sys").argv[1:])'
        def execute_as(uid):
            def identity():
                os.setgid(uid)
                os.setuid(uid)
            return subprocess.run([sys.executable, '-c', code, str(root), str(identifier)],
                preexec_fn=identity, capture_output=True, text=True, timeout=15)
        api = execute_as(1000)
        assert api.returncode and 'PermissionError' in api.stderr and target.exists()
        native = execute_as(1001)
        assert native.returncode == 0, native.stderr
        assert not target.exists()
