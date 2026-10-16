"""Pinned 0.2.38 studio images cutover; no migration or context restoration.

CLI: RELEASE build|prepare|deploy. Reuse tested image/capacity gates, the complete
Compose chain, drained backup and fail-closed release. Never replay failed deploy.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('images_cutover', Path(__file__).with_name('overseas-attachments-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d = a.d
d.TARGET_VERSION, d.BASE_VERSION = '0.2.38', '0.2.37'
d.DOMESTIC_MIGRATION = '0029'
d.RELEASE_PATTERN = r'overseas-20261016-[0-9a-f]{7}'
d.MIGRATION_RECOVERY = (' This release performs no database migration or context restoration. '
    'Keep intake closed on failure, inspect the actual phase and queues before recovery. '
    'Preserve domestic workers, deletion service, identity, Skills and conversation history.')
BASE_RELEASE = 'overseas-20261015-726ede0'
BASE_FRONTEND_RELEASE = 'domestic-20261015-4c64c1a'
BASE_NATIVE = Path('/opt/hengxin-overseas-releases') / BASE_RELEASE / 'backend'
DOMESTIC_NATIVE = Path('/opt/hengxin-native-releases') / BASE_FRONTEND_RELEASE / 'backend'
DELETION_UNIT = 'hengxin-domestic-deletions'
SYSTEMD = Path('/etc/systemd/system')
_validate, _public = d.validate, d.verify.public
REQUIRED = {'scripts/release/overseas-images-deploy.py',
    'backend/migrations/versions/0029_api_task_deletions.py',
    'backend/app/overseas/studio/image_edits.py',
    'backend/tests/test_studio_image_edits.py',
    'backend/tests/test_studio_image_preview.py'}


def validate(work, release):
    source, manifest, image = _validate(work, release)
    assert REQUIRED <= manifest['files'].keys(), 'Images release runtime missing from manifest'
    return source, manifest, image


def schemas():
    assert d.r.sql('SELECT version_num FROM alembic_version') == d.DOMESTIC_MIGRATION
    assert d.u.sql('SELECT version_num FROM overseas_alembic_version') == d.TARGET_MIGRATION
    assert d.u.sql(a.USAGE_COLUMN) == '0', 'Overseas usage column still exists'


def normalize_exec_start(value):
    """Discard only systemd execution statistics, never executable/argv/settings.

    daemon-reload may reset these statistics while MainPID and /proc remain
    unchanged. Unknown formats remain unchanged and therefore fail closed.
    """
    return re.sub(
        r'(\{ path=.*? ; argv\[\]=.*? ; ignore_errors=(?:yes|no))'
        r' ; start_time=[^;{}]* ; stop_time=[^;{}]* ; pid=\d+'
        r' ; code=[^;{}]* ; status=[^;{}]* \}', r'\1 }', value)


def native_state(unit, expected):
    d.m.run('systemctl', 'is-active', unit)
    show = lambda key: d.m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True)
    cwd, pid = show('WorkingDirectory'), int(show('MainPID'))
    assert Path(cwd) == expected, 'Native release baseline drift: ' + unit
    assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == expected, 'Native running process drift: ' + unit
    fields = {key: show(key) for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles', 'ExecStart', 'User')}
    fields['ExecStart'] = normalize_exec_start(fields['ExecStart'])
    files = {part for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles')
             for part in fields[key].split() if Path(part).is_absolute()}
    expected_user = 'hengxin-overseas' if unit in d.u.UNITS else 'codex'
    assert fields['FragmentPath'] and fields['User'] == expected_user, 'Native unit/user drift: ' + unit
    return dict(pid=pid, cwd=cwd, fields=fields, files={p: d.m.digest(p) for p in sorted(files)})


def domestic_native():
    return {unit: native_state(unit, DOMESTIC_NATIVE) for unit in (d.m.UNITS[0], DELETION_UNIT)}


def preflight():
    assert json.loads((d.m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    assert json.loads((d.m.APP / 'FRONTEND_RELEASE.json').read_text())['release'] == BASE_FRONTEND_RELEASE, 'Frontend release baseline drift'
    assert json.loads((d.m.APP / 'OVERSEAS_RELEASE.json').read_text())['release'] == BASE_RELEASE, 'Overseas release baseline drift'
    live = d.m.live(d.u.API)
    assert live['State']['Running'] and live['State']['Health']['Status'] == 'healthy'
    assert live['HostConfig']['Memory'] == d.resources.API_MEMORY, 'API memory baseline drift'
    for unit in d.u.UNITS:
        native_state(unit, BASE_NATIVE)
        folder = SYSTEMD / (unit + '.service.d')
        pointer = folder / d.u.DROP
        assert pointer.read_text() == a.native_pointer(BASE_NATIVE, unit), 'Native pointer baseline drift'
        effective = d.m.run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value', capture=True).split()
        assert str(pointer) in effective, 'Native pointer is not loaded'
        assert all(Path(path).name <= d.u.DROP for path in effective), 'Higher priority native override'
        assert all(path.name <= d.u.DROP for path in folder.glob('*.conf')), 'Unloaded native override'
    domestic_native()
    for path in (d.m.EDGE, d.proxy.inner(d.m)):
        a.proxy_baseline(path.read_text())


def before_switch(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()  # Read-only: no migration, Skill installation or context recovery.


def wait_edge(paths, expected, timeout=30):
    """Bound both each HTTP probe and asynchronous Nginx reload to one deadline."""
    deadline = time.monotonic() + timeout
    while True:
        matched = True
        for path in paths:
            for options in (('--resolve', 'zhitu.qhhengxin.top:443:127.0.0.1'), ()):
                remaining = deadline - time.monotonic()
                assert remaining > 0, 'Overseas edge did not reach HTTP ' + expected
                limit = min(5, remaining)
                try:
                    code = d.m.run('curl', '--max-time', str(limit), '-sS', '-o', '/dev/null',
                        '-w', '%{http_code}', *options, d.r.ORIGIN + path, capture=True, timeout=limit)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    code = ''
                matched = matched and code == expected
        assert time.monotonic() < deadline, 'Overseas edge did not reach HTTP ' + expected
        if matched:
            return
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))


def closed(timeout=30):
    wait_edge(('/api/overseas/v1/auth/me', '/api/overseas/v1/tasks'), '503', timeout)


def public():
    wait_edge(('/api/overseas/v1/health/ready',), '200')
    _public()


d.validate = validate
d.schemas = d.installed_schemas = schemas
d.preflight, d.before_switch = preflight, before_switch
d.domestic_native, d.closed = domestic_native, closed
d.verify.public = public
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
