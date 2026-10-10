"""Installed API/asset verification with a short-lived read-only authorized check."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

CONTRACT_CHECK = r'''
import json
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.main import app
from app.db.session import get_session, session_factory
from app.modules.auth.dependencies import get_identity_id
from app.resource_models import UserRecord
with session_factory()() as session:
    session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    user = session.scalar(select(UserRecord).where(UserRecord.status == 'active',
        UserRecord.role == 'super_admin', UserRecord.identity_source != 'development'))
    assert user is not None, 'No authorized production administrator'
    # No persisted session/token; overrides exist only in this verification process.
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_identity_id] = lambda: user.id
    client = TestClient(app)
    def get(path):
        response = client.get('/api/v1' + path)
        assert response.status_code == 200, (path, response.status_code)
        return response.json()
    path = '/management/api-usage?outputsOnly=true&pageSize=100'
    report = get(path)
    s = report['summary']
    assert report['scope'] == 'all'
    assert s['totalGeneratedImages'] == s['initialImages'] + s['modifiedImages']
    assert sum(r['summary']['totalGeneratedImages'] for r in report['rows']) == s['totalGeneratedImages']
    images = sum(e['generatedImages'] for e in report['events'])
    tasks = {e['taskId'] for e in report['events']}
    for page in range(2, (report['total'] + 99) // 100 + 1):
        detail = get(path + '&page=' + str(page))
        assert detail['summary'] == s
        images += sum(e['generatedImages'] for e in detail['events'])
        tasks.update(e['taskId'] for e in detail['events'])
    assert images == s['totalGeneratedImages'] and len(tasks) == s['generatedTasks']
    typed = {kind: get(path + '&generationType=' + kind)['summary']['totalGeneratedImages']
             for kind in ('initial', 'api_edit', 'cli_edit')}
    assert typed['initial'] == s['initialImages']
    assert typed['api_edit'] + typed['cli_edit'] == s['modifiedImages']
    pages = {str(size): get('/api-image-edits/tasks?view=summary&page=1&pageSize=' + str(size))
             for size in (20, 50, 100)}
    total = pages['20']['total']
    for size, result in pages.items():
        assert result['total'] == total and result['pageSize'] == int(size)
        assert len(result['items']) == min(total, int(size))
    assert [r['id'] for r in pages['20']['items']] == [r['id'] for r in pages['100']['items'][:20]]
    assert [r['id'] for r in pages['50']['items']] == [r['id'] for r in pages['100']['items'][:50]]
    filtered = get('/api-image-edits/tasks?view=summary&pageSize=100&status=succeeded')
    assert all(r['status'] == 'succeeded' for r in filtered['items'])
    second = get('/api-image-edits/tasks?view=summary&page=2&pageSize=20')
    assert not {r['id'] for r in second['items']} & {r['id'] for r in pages['20']['items']}
    monitor = get('/management/api-monitor')
    assert all(c['state'] == 'available' and c['queueState'] == 'available' for c in monitor['channels'])
    settings = get('/management/execution-settings')
    assert not settings['retention']['enabled']
    print(json.dumps(dict(summary=s, generationTypes=typed, dailyRows=len(report['rows']),
        generationEvents=report['total'], recordTotal=total,
        pageSizes={size: len(result['items']) for size,result in pages.items()},
        channels={c['channel']: c['state'] for c in monitor['channels']},
        readOnly=True, routeChecks=True)))
    client.close()
    app.dependency_overrides.clear()
'''


def run(*args, input=None):
    return subprocess.check_output(args, input=input, text=True).strip()


def main():
    release = sys.argv[1]
    assert re.fullmatch(r'usage-total-20261010-[0-9a-f]{7}', release)
    assert sys.argv[2:] in ([], ['--api-only'])
    api_only = sys.argv[2:] == ['--api-only']
    work = Path('/opt/hengxin-releases') / release
    app = Path('/opt/hengxin-smart-image')
    manifest = json.loads((work / 'src/release.json').read_text())
    assert manifest['release'] == release and manifest['migration'] == '0026'
    assert manifest['frontendVersion'] == '0.2.21' and manifest['services'] == ['api']
    prefix = 'hengxin-vps-staging-'
    live = json.loads(run('docker', 'inspect', prefix + 'api-1'))[0]
    assert live['Image'] == (work / 'INSTALL_TEST_IMAGE_ID').read_text().strip()
    assert live['State']['Running'] and live['State']['Health']['Status'] == 'healthy'
    backend = {n.removeprefix('backend/'): h for n,h in manifest['files'].items() if n.startswith('backend/')}
    check = 'import json,sys,hashlib;from pathlib import Path;d=json.load(sys.stdin);assert all(hashlib.sha256((Path("/app")/n).read_bytes()).hexdigest()==h for n,h in d.items());print(len(d))'
    count = int(run('docker', 'exec', '-i', prefix+'api-1', 'python', '-c', check, input=json.dumps(backend)))
    contracts = json.loads(run('docker', 'exec', prefix+'api-1', 'python', '-c', CONTRACT_CHECK))
    schema = run('docker','exec',prefix+'postgres-1','psql','-U','hengxin','-d','hengxin','-Atc','SELECT version_num FROM alembic_version')
    assert schema == '0026'
    readiness = json.loads(run('curl', '--retry', '5', '--retry-delay', '1', '-fsS', 'http://127.0.0.1:18008/api/v1/health/ready'))
    result = dict(release=release, commit=manifest['commit'], schema=schema, backendFiles=count,
                  management=contracts, ready=readiness, frontendVersion=manifest['frontendVersion'])
    if api_only:
        print(json.dumps(result, indent=2)); return
    for name in ('API_RELEASE.json', 'FRONTEND_RELEASE.json', 'USAGE_TOTAL_RELEASE.json'):
        marker = json.loads((app/name).read_text())
        assert all(marker[k] == manifest[k] for k in ('release','commit','frontendVersion','files')), name
    front = {n: h for n,h in manifest['files'].items() if n.startswith('frontend/')}
    assert all(hashlib.sha256((app/n).read_bytes()).hexdigest() == h for n,h in front.items())
    public = 'https://zhitu.qhhengxin.top'
    with urllib.request.urlopen(public+'/', timeout=30) as response:
        html = response.read()
    assert hashlib.sha256(html).hexdigest() == manifest['files']['frontend/dist/index.html']
    assets = re.findall(r'(?:src|href)="(/assets/[^"?]+\.(?:js|css))"', html.decode())
    assert len(assets) >= 2
    for path in assets:
        with urllib.request.urlopen(public+path, timeout=30) as response:
            assert hashlib.sha256(response.read()).hexdigest() == manifest['files']['frontend/dist'+path]
    for path in ('/management/api-usage', '/api-image-edits/tasks?pageSize=100'):
        status = run('curl','-sS','-o','/dev/null','-w','%{http_code}',public+'/api/v1'+path)
        assert status == '401', (path,status)
    result.update(frontendFiles=len(front), publicEntryHash=True, publicAssets=len(assets), anonymousAuth=401)
    (work/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
