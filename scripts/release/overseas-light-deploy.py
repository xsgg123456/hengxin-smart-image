"""Deploy only the overseas HTTP API and shared frontend; retain workers and data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

from importlib.util import module_from_spec, spec_from_file_location


def load(name):
    spec = spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scope = load('overseas-light-runtime')
r = scope.r
gate = load('skill-reuse-gate')
gate.r = r
frontend = load('sku-frontend')
frontend.r = r
frontend.BASE_VERSION = '0.2.66'
ready = load('image-cache-runtime').readiness

CONTRACT = r'''
import json
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.db.session import get_session, session_factory
from app.overseas.auth.dependencies import get_current_member
from app.overseas.auth.models import Member, MemberRole
from app.overseas.main import app
with session_factory()() as session:
    session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    actor = session.scalar(select(Member).join(MemberRole, MemberRole.user_id == Member.id).where(
        MemberRole.role == 'super_admin', Member.status == 'active', Member.directory_state == 'enrolled').limit(1))
    assert actor is not None
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_member] = lambda: actor
    client = TestClient(app)
    def get(path):
        response = client.get('/api/overseas/v1' + path)
        assert response.status_code == 200, (path, response.status_code)
        return response.json()
    persons = get('/management/people')['items']
    jobs = get('/management/jobs?pageSize=20')
    assignees = get('/task-assignees')['items']
    first = get('/tasks?pageSize=20')
    second = get('/tasks?pageSize=20&page=2')
    assert len(first['items']) <= 20 and len(second['items']) <= 20 and first['total'] == second['total']
    assert not {t['id'] for t in first['items']} & {t['id'] for t in second['items']}
    designing = get('/tasks?statusGroup=designing&pageSize=20')
    if assignees:
        selected = get('/tasks?designerId=' + assignees[0]['id'] + '&pageSize=20')
        assert all(t['designer'] and t['designer']['id'] == assignees[0]['id'] for t in selected['items'])
    operators = get('/archive-operators')['items']
    archives = get('/archives?pageSize=20')
    if operators:
        get('/archives?archiverId=' + operators[0]['id'] + '&pageSize=20')
    assert all(p['calls'] > 0 for p in persons)
    print(json.dumps({'people': len(persons), 'jobs': jobs['total'], 'tasks': first['total'],
        'designing': designing['total'], 'assignees': len(assignees), 'archives': archives['total'],
        'archivers': len(operators), 'readOnly': True}))
    client.close()
    app.dependency_overrides.clear()
'''


def state(work, tested=False):
    data = json.loads((work / 'prepared.json').read_text())
    source = Path(data['source'])
    manifest = r.verify_package(source)
    r.require(r.digest(source / 'release.json') == data['manifest'], 'Manifest drift')
    r.require(all(r.digest(p) == h for p, h in data['compose']['files'].items()), 'Compose drift')
    r.require(r.digest(work / 'api-overlay.json') == data['overlayHash'], 'API overlay drift')
    r.require(r.hashes(data['image']) == {n: v['sha256'] for n, v in manifest['api']['files'].items()},
              'Candidate image drift')
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    r.unchanged(data['protected'])
    gate.guard(work, data)
    if tested:
        r.require(json.loads((work / 'INSTALL_TESTS_PASSED').read_text()) ==
                  {'manifest': data['manifest'], 'image': data['image']}, 'Installed test proof missing')
    return data, source


def prepare(work, source):
    r.require(not (work / 'prepared.json').exists(), 'Existing preparation')
    manifest, live = r.verify_package(source), r.inspect()
    r.require(live['State']['Running'] and live['Image'] == manifest['api']['image'], 'Live API image drift')
    r.require(r.hashes(live['Image']) == {n: v['baseline'] for n, v in manifest['api']['files'].items()},
              'Live API source differs from reviewed parent')
    protected = r.b.snapshot()
    r.require(protected['frontendVersion'] == frontend.BASE_VERSION, 'Frontend baseline drift')
    r.require(r.sql(r.DB, 'SELECT version_num FROM overseas_alembic_version') == r.REVISION, 'Schema drift')
    data = dict(source=str(source), manifest=r.digest(source / 'release.json'), oldId=live['Id'],
                oldImage=live['Image'], compose=r.a.compose_info(live), protected=protected)
    before = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json'))
    r.a.check_live_config(live, before)
    context = work / 'api-build'
    context.mkdir(mode=0o755)
    for name in sorted(r.FILES):
        target = context / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / 'api' / name, target)
    for path in context.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    tag = 'hengxin-smart-image-backend:' + manifest['release']
    r.require(not r.run('docker', 'images', '-q', tag), 'Release tag already exists')
    r.run('docker', 'tag', live['Image'], tag + '-base')
    (context / 'Dockerfile').write_text('FROM ' + tag + '-base\n' +
        ''.join('COPY ' + n + ' /app/' + n + '\n' for n in sorted(r.FILES)))
    r.run('docker', 'build', '--network=none', '--pull=false', '-t', tag, str(context), timeout=180)
    data['image'] = r.run('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
    r.private(work / 'api-overlay.json', {'services': {'api': {'image': data['image']}}})
    r.private(work / 'old-overlay.json', {'services': {'api': {'image': data['oldImage']}}})
    after = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=work / 'api-overlay.json'))
    before['services']['api']['image'] = data['image']
    r.require(before == after, 'Overlay changes unrelated configuration')
    data['overlayHash'] = r.digest(work / 'api-overlay.json')
    data['oldOverlayHash'] = r.digest(work / 'old-overlay.json')
    data['proxies'] = gate.save(work)
    r.private(work / 'prepared.json', data)
    state(work)
    return 'PREPARED_NO_LIVE_SERVICE_CHANGED'


def test(work):
    data, source = state(work)
    name = 'hx-light-test-' + data['manifest'][:12]
    created = False
    try:
        image = json.loads(r.run('docker', 'inspect', r.PG))[0]['Image']
        r.run('docker', 'run', '--rm', '-d', '--network', 'none', '--name', name,
              '--mount', 'type=volume,dst=/var/lib/postgresql/data', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image)
        created = True
        deadline = time.monotonic() + 45
        while True:
            try:
                r.run('docker', 'exec', name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', timeout=4)
                break
            except RuntimeError:
                r.require(time.monotonic() < deadline, 'Isolated PostgreSQL readiness timeout')
                time.sleep(.5)
        r.run('docker', 'exec', name, 'createdb', '-h', '127.0.0.1', '-U', 'postgres', 'light_test')
        url = 'postgresql+psycopg://postgres@127.0.0.1/light_test'
        command = ['docker', 'run', '--rm', '--network', 'container:' + name, '--read-only', '--tmpfs', '/tmp:rw,nosuid',
            '--mount', 'type=bind,src=' + str(source / 'tests') + ',dst=/app/tests,readonly',
            '-e', 'PYTHONPATH=/app', '-e', 'TEST_OVERSEAS_MEMBERS_DATABASE_URL=' + url,
            '--entrypoint', 'python', data['image'], '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
            *['/app/tests/' + n for n in scope.TESTS]]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        r.private(work / 'installed-tests.txt', result.stdout + '\n--- STDERR ---\n' + result.stderr)
        r.require(result.returncode == 0 and 'passed' in result.stdout and 'failed' not in result.stdout and
                  'skipped' not in result.stdout, 'Isolated installed tests failed; inspect private log')
        r.private(work / 'INSTALL_TESTS_PASSED', {'manifest': data['manifest'], 'image': data['image']})
        return result.stdout.strip().splitlines()[-1]
    finally:
        if created:
            r.run('docker', 'rm', '-f', '-v', name)


def verify_api(data):
    live = r.inspect()
    r.require(live['Image'] == data['image'] and live['State']['Running'], 'Candidate API not running')
    config = json.loads(r.a.compose(data['compose'], 'config', '--format', 'json', overlay=Path(data['overlay'])))
    r.a.check_live_config(live, config)
    ready('http://127.0.0.1:18018/api/overseas/v1/health/ready')
    return json.loads(r.run('docker', 'exec', r.API, 'python', '-B', '-c', CONTRACT, timeout=90))


def verify_public(source):
    manifest = r.verify_package(source)
    with urllib.request.urlopen('https://zhitu.qhhengxin.top/', timeout=30) as response:
        body = response.read()
    r.require(hashlib.sha256(body).hexdigest() == manifest['files']['frontend/dist/index.html'], 'Public HTML drift')
    assets = re.findall(r'(?:src|href)="(/assets/[^"?]+\.(?:js|css))"', body.decode())
    r.require(any(path.endswith('.js') for path in assets), 'Public entry has no JavaScript asset')
    for path in assets:
        with urllib.request.urlopen('https://zhitu.qhhengxin.top' + path, timeout=30) as response:
            r.require(hashlib.sha256(response.read()).hexdigest() == manifest['files']['frontend/dist' + path],
                      'Public asset drift')
    r.require(r.run('curl', '--max-time', '10', '-sS', '-o', '/dev/null', '-w', '%{http_code}',
        'https://zhitu.qhhengxin.top/api/overseas/v1/management/people') == '401', 'Anonymous access drift')
    ready('https://zhitu.qhhengxin.top/api/overseas/v1/health/ready')


def deploy(work):
    data, source = state(work, tested=True)
    r.require(r.inspect()['Id'] == data['oldId'], 'API baseline identity changed')
    r.require(r.digest(work / 'old-overlay.json') == data['oldOverlayHash'], 'Rollback overlay drift')
    r.require(not (work / 'SWITCH_STARTED').exists(), 'Inspect previous switch attempt')
    data['overlay'] = str(work / 'api-overlay.json')
    backup = work / 'frontend-backup'
    gate_started = api_started = stop_confirmed = front_started = False
    try:
        r.private(work / 'SWITCH_STARTED', {'manifest': data['manifest'], 'oldId': data['oldId']})
        gate_started = True
        gate.set_gate(work, data, True)
        api_started = True
        # Never escalate to SIGKILL; nginx has already drained old requests.
        r.run('docker', 'stop', '--time', '-1', r.API, timeout=90)
        stop_confirmed = True
        r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api', overlay=work / 'api-overlay.json')
        contracts = verify_api(data)
        r.unchanged(data['protected'])
        front_started = True
        frontend.deploy(source, r.a.APP, backup)
        gate.set_gate(work, data, False)
        verify_public(source)
        r.unchanged(data['protected'])
        r.private(work / 'VERIFIED.json', {'manifest': data['manifest'], 'image': data['image'], 'contracts': contracts})
        return 'DEPLOYED_AND_VERIFIED ' + json.dumps(contracts, ensure_ascii=False)
    except BaseException:
        if gate_started:
            try:
                if api_started:
                    # A timed-out docker stop may still be running in the daemon.
                    # Never race it by replacing the container or reopening traffic.
                    r.require(stop_confirmed or not r.inspect()['State']['Running'],
                              'Graceful API stop is still pending')
                    gate.set_gate(work, data, True)
                    if front_started and (backup / 'COMPLETE.json').exists():
                        frontend.rollback(r.a.APP, backup)
                    r.a.compose(data['compose'], 'up', '-d', '--no-deps', '--no-build', 'api', overlay=work / 'old-overlay.json')
                    r.require(r.inspect()['Image'] == data['oldImage'], 'Original API image not restored')
                    ready('http://127.0.0.1:18018/api/overseas/v1/health/ready')
                gate.set_gate(work, data, False)
                r.unchanged(data['protected'])
                print('ROLLBACK_COMPLETE_WORKERS_AND_DATABASE_RETAINED', flush=True)
            except BaseException:
                print('ROLLBACK_REQUIRES_INSPECTION: ' + str(work), flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'test', 'deploy'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    args.work.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (args.work / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            r.require(args.source is not None, 'Source required')
            result = prepare(args.work, args.source.resolve())
        else:
            result = globals()[args.action](args.work)
        print(result, flush=True)


if __name__ == '__main__':
    main()
