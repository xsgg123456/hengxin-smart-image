"""Pinned 0.2.34 -> 0.2.35 studio/admin release with forward-only overseas_0016 migration.

Reuse the tested upload cutover, preserving its installed 3 GiB / 500 MB settings
and the effective 99 native pointer. Failure requires inspected recovery, not replay.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('attachment_cutover', Path(__file__).with_name('overseas-upload-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
d.TARGET_VERSION, d.BASE_VERSION = '0.2.35', '0.2.34'
d.RELEASE_PATTERN = r'overseas-20261015-[0-9a-f]{7}'
d.TARGET_MIGRATION = 'overseas_0016'
d.MIGRATION_RECOVERY = (' This release drops overseas_jobs.usage. Once MIGRATION_STARTED exists, '
    'never restore old application code or downgrade automatically. Keep intake closed, inspect the actual '
    'revision and column state, and use reviewed forward recovery with the new runtime. Restoring the '
    'verified full database backup requires a separate reviewed recovery and proof of no subsequent writes.')
d.u.DROP = '99-overseas-upload.conf'
SYSTEMD = Path('/etc/systemd/system')


def native_pointer(target, unit):
    command = (str(target / '.venv/bin/celery') + ' -A app.overseas.execution.worker:celery_app worker '
               '--pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
               if unit.endswith('worker') else str(target / '.venv/bin/python') + ' -m app.overseas.execution.outbox')
    return '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + command + '\n'


def proxy_baseline(body):
    matches = list(re.finditer(d.proxy.LOCATION, body))
    assert len(matches) == 1, 'Exactly one overseas proxy location required'
    location = matches[0].group()
    assert re.search(r'\bproxy_pass\s+http://[^;]+;', location), 'Existing upstream required'
    for key, value in d.proxy.DIRECTIVES.items():
        assert re.findall(r'\b' + key + r'\s+([^;{}]+);', location) == [value], 'Proxy baseline drift: ' + key


def preflight():
    assert json.loads((d.m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    assert json.loads((d.m.APP / 'OVERSEAS_RELEASE.json').read_text())['release'] == 'overseas-20261014-3b09fbc', 'Overseas release baseline drift'
    live = d.m.live(d.u.API)
    assert live['State']['Running'] and live['State']['Health']['Status'] == 'healthy'
    assert live['HostConfig']['Memory'] == d.resources.API_MEMORY, 'API memory baseline drift'
    for unit in d.u.UNITS:
        target = Path(d.m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True))
        folder = SYSTEMD / (unit + '.service.d')
        pointer = folder / d.u.DROP
        assert pointer.read_text() == native_pointer(target, unit), 'Native pointer baseline drift'
        # Include vendor/runtime drop-ins, not just files under /etc.
        effective = d.m.run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value', capture=True).split()
        assert str(pointer) in effective, 'Native pointer is not loaded'
        assert all(Path(path).name <= d.u.DROP for path in effective), 'Higher priority native override'
        assert all(path.name <= d.u.DROP for path in folder.glob('*.conf')), 'Unloaded native override'
    for path in (d.m.EDGE, d.proxy.inner(d.m)):
        proxy_baseline(path.read_text())


def prepare_proxy(work, source, m):
    directives = dict(re.findall(r'^(\w+)\s+([^;]+);$', (source / 'infra/nginx.overseas-upload.inc').read_text(), re.M))
    assert directives == d.proxy.DIRECTIVES, 'Packaged upload directive drift'
    for label, path in (('edge', m.EDGE), ('inner', d.proxy.inner(m))):
        before = path.read_text()
        proxy_baseline(before)
        # Preserve exact existing bytes; this release changes no proxy setting.
        for stage in ('before', 'after'):
            m.private(work / f'upload-{label}-{stage}.conf', before)


USAGE_COLUMN = ("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='overseas_jobs' AND column_name='usage'")


def installed_schemas():
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert d.u.sql('SELECT version_num FROM overseas_alembic_version') == d.TARGET_MIGRATION
    assert d.u.sql(USAGE_COLUMN) == '0', 'Overseas usage column still exists'


def migrate(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').exists(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').exists(), 'Executors were not drained and stopped'
    d.schemas()
    assert d.u.sql(USAGE_COLUMN) == '1', 'Unexpected overseas usage baseline'
    # Separate owner-role migration service; keep the API-only deployment overlay unchanged.
    overlay = work / 'overseas-migration-overlay.json'
    d.m.private(overlay, {'services': {'migrate': {'image': identity,
        'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}})
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    current = json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json', capture=True))
    assert before == current, 'Migration Compose baseline drift'
    after = json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json',
                                   overlay=overlay, capture=True))
    d.m.same_settings(before, after, ['migrate'])
    assert after['services']['migrate']['image'] == identity, 'Migration image drift'
    d.m.private(work / 'MIGRATION_STARTED', d.MIGRATION_RECOVERY)
    d.m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never',
                'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', d.TARGET_MIGRATION,
                overlay=overlay)
    installed_schemas()
    d.m.private(work / 'MIGRATION_VERIFIED', d.TARGET_MIGRATION + ': overseas_jobs.usage absent')


d.before_switch = migrate
d.installed_schemas = installed_schemas
d.preflight = preflight
d.proxy.prepare = prepare_proxy
main = d.main


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
