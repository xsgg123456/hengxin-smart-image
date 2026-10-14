"""Pinned 0.2.32 overseas preparation and installed checks; no domestic mutation."""
import importlib.util
import json
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('studio_hotfix', Path(__file__).with_name('overseas-hotfix-deploy.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
m, u, r, verify = h.m, h.u, h.r, h.verify
VERSION, PREVIOUS = '0.2.32', '0.2.31'
OLD_SCHEMA, NEW_SCHEMA = 'overseas_0014', 'overseas_0015'


def validate(work, release):
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == VERSION
    assert manifest['migration'] == '0028' and manifest['overseasMigration'] == NEW_SCHEMA
    assert json.loads((source / 'frontend/package.json').read_text())['version'] == VERSION
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def schemas(expected):
    assert r.sql('SELECT version_num FROM alembic_version') == '0028', 'Domestic schema drift'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == expected, 'Overseas schema drift'


def previous_version():
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == PREVIOUS, 'Previous version drift'
    assert json.loads((m.APP / 'OVERSEAS_RELEASE.json').read_text())['frontendVersion'] == PREVIOUS, 'Overseas release drift'


def overlay(source, identity):
    return {'services': {name: {'image': identity, 'build': {
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}} for name in ('api', 'migrate')}}


def prepared_settings(work, data, identity, source):
    path = work / 'overseas-overlay.json'
    assert json.loads(path.read_text()) == overlay(source, identity), 'Prepared overlay drift'
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    current = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', capture=True))
    assert before == current, 'Prepared Compose baseline drift'
    after = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', overlay=path, capture=True))
    m.same_settings(before, after, ['api', 'migrate'])


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    schemas(OLD_SCHEMA)
    previous_version()
    m.assets_safe(source)
    data = m.topology()
    assert data['overseas']['env'], 'Explicit overseas Compose env file required for backup'
    assert data['native'][u.UNITS[0]] == data['native'][u.UNITS[1]]
    native = h.domestic_native()
    result = h.evidence(work)
    h.drain.idle(result['workers'])
    m.private(work / 'prepare-queues.json', result)
    m.private(work / 'topology.json', data)
    m.private(work / 'domestic-native.json', native)
    for group in m.GROUPS:
        config = json.loads(m.compose(data[group], 'config', '--format', 'json', capture=True))
        m.check_live_config(group, config)
        m.private(work / (group + '-compose.private.json'), config)
    m.private(work / 'overseas-overlay.json', overlay(source, identity))
    prepared_settings(work, data, identity, source)
    target = u.prepare_native(source, manifest['release'])
    r.hashes(target.parent, {'files': {n: v for n, v in manifest['files'].items() if n.startswith('backend/')}})
    m.skills.verify(u, work, target)
    m.private(work / 'native-target', str(target))
    assert m.topology() == data and h.domestic_native() == native, 'Production topology drift during preparation'
    m.private(work / 'PREPARED', identity)


def migrate(work, data, identity, image):
    # Recheck the installation-tested image immediately before the irreversible boundary.
    assert m.image_id(work, image) == identity, 'Approved image drift'
    schemas(OLD_SCHEMA)
    m.private(work / 'MIGRATION_STARTED', 'Forward-only; no automatic downgrade or old-runtime restore')
    m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never',
              'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', NEW_SCHEMA,
              overlay=work / 'overseas-overlay.json')
    schemas(NEW_SCHEMA)
    m.private(work / 'MIGRATION_VERIFIED', NEW_SCHEMA)


def installed(work, manifest, identity, data, native, target):
    schemas(NEW_SCHEMA)
    expected = {n.removeprefix('backend/'): v for n, v in manifest['files'].items() if n.startswith('backend/')}
    assert expected
    actual = m.live(u.API)
    assert actual['State']['Running'] and actual['Image'] == identity
    assert actual['Mounts'] == data['overseas']['mounts'][u.API]
    code = ('import hashlib,json,sys; from pathlib import Path; m=json.loads(sys.argv[1]); '
            'assert all(hashlib.sha256((Path("/app")/n).read_bytes()).hexdigest()==h for n,h in m.items())')
    m.run('docker', 'exec', u.API, 'python', '-c', code, json.dumps(expected))
    for unit in u.UNITS:
        m.run('systemctl', 'is-active', unit)
        assert m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True) == str(target)
        pid = int(m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
        assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == target
    r.hashes(target.parent, {'files': {'backend/' + n: v for n, v in expected.items()}})
    u.wait_worker_ready()
    h.wait_empty(work, 'installed-idle')
    h.resources_unchanged(data, native, {'native': target, 'overlay': work / 'overseas-overlay.json'})
    m.skills.verify(u, work, target)
    for port, route in verify.HEALTH.values():
        verify.get(f'http://127.0.0.1:{port}' + route)
    for route in ('auth/me', 'tasks', 'members/applications', 'studio/sessions'):
        assert verify.status('http://127.0.0.1:18018/api/overseas/v1/' + route) in ('401', '403')
    m.private(work / 'INSTALLED_VERIFIED', 'Image/native hashes, schema, sandbox Skills and untouched services verified')


def failure(work, phase, exc, edge, data):
    # Record actual outcomes even when nginx/API closure or schema queries also fail.
    evidence = dict(phase=phase, errorType=type(exc).__name__, edgeClosed=False, apiStopped=False,
                    migrationStarted=(work / 'MIGRATION_STARTED').exists(),
                    recovery='Inspect RECOVERY.txt; forward recovery only; no database restore or executor stop')
    for key, operation in (
        ('edgeClosed', lambda: (h.close_edge(edge), h.closed())),
        ('apiStopped', lambda: m.compose(data['overseas'], 'stop', '-t', '30', 'api',
                                        overlay=work / 'overseas-overlay.json'))):
        try:
            operation()
            evidence[key] = True
        except BaseException as error:
            evidence[key + 'Error'] = type(error).__name__
    for key, sql, query in (
        ('domesticSchema', r.sql, 'SELECT version_num FROM alembic_version'),
        ('overseasSchema', u.sql, 'SELECT version_num FROM overseas_alembic_version')):
        try:
            evidence[key] = sql(query)
        except BaseException as error:
            evidence[key] = 'unavailable:' + type(error).__name__
    m.private(work / 'FAILURE.json', evidence)
