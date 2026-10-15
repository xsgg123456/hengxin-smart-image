"""Pinned 0.2.35 -> 0.2.36 file continuity release; no database migration.

Reuse the installed upload capacity, backup, drain and retention protections.
Only the explicitly listed conversations are recovered, before runtime cutover.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import UUID

spec = importlib.util.spec_from_file_location('context_cutover', Path(__file__).with_name('overseas-attachments-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d = a.d
d.TARGET_VERSION, d.BASE_VERSION = '0.2.36', '0.2.35'
d.MIGRATION_RECOVERY = (' This release performs no database migration. Keep intake closed after a recovery failure; '
    'inspect context recovery evidence before retrying. Preserve source round directories and recovered work. '
    'Application rollback requires reviewed handling of persistent work and a new inventory of any later rounds; '
    'never trust an earlier recovery marker after a rollback.')
BASE_RELEASE = 'overseas-20261015-adf861b'
BASE_NATIVE = Path('/opt/hengxin-overseas-releases') / BASE_RELEASE / 'backend'
SYSTEMD = Path('/etc/systemd/system')
REQUIRED = {
    'backend/app/execution/persistent_mounts.py',
    'backend/app/overseas/studio/context_assets.py',
    'backend/app/overseas/studio/context_fs.py',
    'backend/app/overseas/studio/context_migration.py',
    'backend/app/overseas/studio/context_workspace.py',
    'backend/app/overseas/studio/restore_context.py',
    'backend/app/overseas/studio/work_baseline.py',
    'backend/tests/studio_context_probe.py',
    'scripts/release/overseas-context-deploy.py',
    'scripts/release/overseas-context-recovery.py',
}
_validate, _prepare, _deploy = d.validate, d.prepare, d.deploy


def validate(work, release):
    source, manifest, image = _validate(work, release)
    assert REQUIRED <= manifest['files'].keys(), 'Context runtime/recovery/probe missing from manifest'
    return source, manifest, image


def preflight():
    assert json.loads((d.m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    assert json.loads((d.m.APP / 'OVERSEAS_RELEASE.json').read_text())['release'] == BASE_RELEASE, 'Overseas release baseline drift'
    live = d.m.live(d.u.API)
    assert live['State']['Running'] and live['State']['Health']['Status'] == 'healthy'
    assert live['HostConfig']['Memory'] == d.resources.API_MEMORY, 'API memory baseline drift'
    for unit in d.u.UNITS:
        d.m.run('systemctl', 'is-active', unit)
        target = Path(d.m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True))
        assert target == BASE_NATIVE, 'Native release baseline drift'
        pid = int(d.m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
        assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == target, 'Native running process drift'
        folder = SYSTEMD / (unit + '.service.d')
        pointer = folder / d.u.DROP
        assert pointer.read_text() == a.native_pointer(target, unit), 'Native pointer baseline drift'
        effective = d.m.run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value', capture=True).split()
        assert str(pointer) in effective, 'Native pointer is not loaded'
        assert all(Path(path).name <= d.u.DROP for path in effective), 'Higher priority native override'
        assert all(path.name <= d.u.DROP for path in folder.glob('*.conf')), 'Unloaded native override'
    for path in (d.m.EDGE, d.proxy.inner(d.m)):
        a.proxy_baseline(path.read_text())


def target_digest(work):
    path = work / 'context-targets.json'
    assert path.is_file() and not path.is_symlink(), 'Explicit context recovery targets required'
    raw = path.read_bytes()
    data = json.loads(raw)
    assert isinstance(data, dict) and set(data) == {'conversationIds'}, 'Invalid context recovery target fields'
    ids = data['conversationIds']
    assert isinstance(ids, list) and ids, 'Nonempty context recovery targets required'
    assert all(isinstance(value, str) and str(UUID(value)) == value for value in ids), 'Canonical context UUIDs required'
    assert len(ids) == len(set(ids)), 'Duplicate context recovery targets'
    return hashlib.sha256(raw).hexdigest()


def frozen_targets(work):
    assert (work / 'CONTEXT_TARGETS_SHA256').read_text() == target_digest(work), 'Context recovery targets changed since prepare'


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists(), 'Release already prepared'
    digest = target_digest(work)
    d.m.private(work / 'CONTEXT_TARGETS_SHA256', digest)
    _prepare(work, source, manifest, image)
    frozen_targets(work)


def deploy(work, source, manifest, image):
    frozen_targets(work)
    _deploy(work, source, manifest, image)


def recovery_module(source):
    spec = importlib.util.spec_from_file_location('context_recovery', source / 'scripts/release/overseas-context-recovery.py')
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    return recovery


def before_switch(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    frozen_targets(work)
    d.schemas()
    marker = work / 'CONTEXT_RECOVERY_VERIFIED'
    assert not marker.exists() and not marker.is_symlink(), 'Previous context recovery requires inspected recovery'
    target = Path((work / 'native-target').read_text())
    recovery_module(source).recover_contexts(work, source, target, data, destination)
    assert marker.is_file() and not marker.is_symlink() and marker.stat().st_size > 0, 'Context recovery was not verified'
    frozen_targets(work)
    d.schemas()


d.validate, d.prepare, d.deploy = validate, prepare, deploy
d.schemas = d.installed_schemas = a.installed_schemas
d.preflight, d.before_switch = preflight, before_switch
main = d.main


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
