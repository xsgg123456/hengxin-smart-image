"""Relocate the three domestic runtimes, preserving live policy and recovery evidence."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('retention_native', Path(__file__).with_name('retention-management-native.py'))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
m, UNIT, DELETE, RETENTION, UNITS = old.m, old.UNIT, old.DELETE, old.RETENTION, old.UNITS
snapshot, snapshots, show, ready = old.snapshot, old.snapshots, old.show, old.ready
target_argv = old.target_argv
SYSTEMD = Path('/etc/systemd/system')
NATIVE_ROOT = Path('/opt/hengxin-native-releases')
DROPIN = 'zzzzz-retention-management.conf'
REQUIRED = {'app/execution/cleanup_paths.py', 'app/execution/cleanup_diagnostics.py',
            'app/retention/paths.py', 'app/modules/api_image_edits/deletion_paths.py'}
SMOKE = '''import os, tempfile
from pathlib import Path
from uuid import uuid4
from app.execution import cleanup_paths, cleanup_diagnostics, credential_broker_client
import app.retention.worker
assert os.getuid() == 1001
assert Path(cleanup_paths.__file__).parent.parent == Path.cwd() / 'app'
with tempfile.TemporaryDirectory(prefix='hengxin-cleanup-smoke-') as directory:
    root = Path(directory)
    resource = uuid4()
    workspace = root / str(resource)
    links = workspace / 'home/.codex/tmp/arg0/codex-arg0Smoke1'
    links.mkdir(parents=True)
    for name in ('apply_patch', 'applypatch', 'codex-execve-wrapper', 'codex-linux-sandbox'):
        (links / name).symlink_to('/opt/codex')
    cleanup_paths.clean(root, resource)
    assert not workspace.exists()
    workspace.mkdir()
    sentinel = root / 'sentinel'
    sentinel.write_text('unchanged')
    (workspace / 'unexpected').symlink_to(sentinel)
    try:
        cleanup_paths.clean(root, resource)
    except cleanup_paths.CleanupSafetyError as error:
        assert error.code == 'UNEXPECTED_LINK'
    else:
        raise AssertionError('Unexpected symlink accepted')
    assert sentinel.read_text() == 'unchanged'
print('NATIVE_CLEANUP_SMOKE_PASS')
'''


def overrides():
    return {str(SYSTEMD / (unit + '.service.d') / DROPIN) for unit in UNITS}


def override_state():
    result = {}
    for name in sorted(overrides()):
        path = Path(name)
        assert not path.is_symlink(), 'Native override must be a regular file'
        result[name] = m.digest(path) if path.exists() else None
    return result


def render(row, target):
    target = str(target)
    assert re.fullmatch(r'/opt/hengxin-native-releases/domestic-record-filters-20261022-[0-9a-f]{7}/backend', target)
    argv = target_argv(row, target)
    assert all(not any(c in arg for c in ('\n', '\r', '"', '\\', '%', '$')) for arg in argv)
    return '[Service]\nWorkingDirectory=' + target + '\nExecStart=\nExecStart=' + ' '.join('"' + a + '"' for a in argv) + '\n'


def code_hashes(work):
    manifest = json.loads((work / 'src/release.json').read_text())
    target = Path((work / 'native-target').read_text())
    assert re.fullmatch(r'domestic-record-filters-20261022-[0-9a-f]{7}', manifest['release'])
    assert target == NATIVE_ROOT / manifest['release'] / 'backend'
    expected = {name.removeprefix('backend/'): value for name, value in manifest['files'].items()
                if name.startswith('backend/')}
    assert REQUIRED <= expected.keys(), 'Shared cleanup files absent from manifest'
    for name, value in expected.items():
        path = target / name
        assert path.resolve().is_relative_to(target.resolve()) and not path.is_symlink()
        assert m.digest(path) == value, 'Native code hash mismatch'


def prepare(work, source, release, rows):
    assert set(rows) == set(UNITS)
    target = m.prepare_domestic_native(source, release, Path(rows[UNIT]['cwd']))
    m.private(work / 'native-target', str(target))
    m.private(work / 'native-snapshots.private.json', rows)
    for unit, row in rows.items():
        m.private(work / (unit + '.conf'), render(row, target))
    code_hashes(work)
    result = m.run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'),
                  '-c', SMOKE, cwd=target, capture=True)
    assert result == 'NATIVE_CLEANUP_SMOKE_PASS', 'Native cleanup smoke failed'
    m.private(work / 'NATIVE_PREPARED', 'Manifest hashes and isolated uid1001 cleanup smoke passed')


def backup(destination, data):
    assert override_state() == data['nativeOverrides'], 'Native overrides drifted before backup'
    rows = {name: dict(digest=digest, contentHex=Path(name).read_bytes().hex() if digest is not None else None)
            for name, digest in data['nativeOverrides'].items()}
    assert all(row['digest'] is None or hashlib.sha256(bytes.fromhex(row['contentHex'])).hexdigest() == row['digest']
               for row in rows.values()), 'Native override changed while backing up'
    m.private(destination / 'native-overrides-before.private.json', rows)


def switch(work, destination):
    assert (destination / 'COMPLETE').exists() and (work / 'NATIVE_PREPARED').exists()
    assert (work / 'EXECUTORS_STOPPED').exists() and (work / 'CLEANUP_STOPPED').exists()
    assert all(show(unit, 'MainPID') == '0' for unit in UNITS), 'Native processes still running'
    saved = json.loads((destination / 'native-overrides-before.private.json').read_text())
    assert set(saved) == overrides()
    assert override_state() == {name: row['digest'] for name, row in saved.items()}, 'Native overrides changed after backup'
    rows = json.loads((work / 'native-snapshots.private.json').read_text())
    assert set(rows) == set(UNITS)
    target = (work / 'native-target').read_text()
    for unit, row in rows.items():
        assert all(m.digest(path) == digest for path, digest in row['files'].items()), 'Native policy drift after drain'
        assert (work / (unit + '.conf')).read_text() == render(row, target), 'Prepared override changed'
    code_hashes(work)
    for unit in UNITS:
        path = SYSTEMD / (unit + '.service.d') / DROPIN
        path.parent.mkdir(exist_ok=True)
        m.private(path, (work / (unit + '.conf')).read_text())
    m.run('systemctl', 'daemon-reload')
    for unit in UNITS:
        assert show(unit, 'WorkingDirectory') == target, 'Native override did not win'


def verify(work):
    old.verify(work)
    rows = json.loads((work / 'native-snapshots.private.json').read_text())
    for unit, before in rows.items():
        path = str(SYSTEMD / (unit + '.service.d') / DROPIN)
        expected = dict(before['files'], **{path: m.digest(work / (unit + '.conf'))})
        assert snapshot(unit)['files'] == expected, 'Native service files changed outside controlled override'
    code_hashes(work)
