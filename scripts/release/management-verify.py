import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

# Run in the deployed API image. Read a real authorized identity without minting
# a session or exposing identity, cookies, model credentials, or business text.
CONTRACT_CHECK = '''
import json
from sqlalchemy import select, text, func
from app.db.session import session_factory
from app.resource_models import UserRecord
from app.contracts.api_usage import UsageQuery, Report
from app.contracts.api_monitor import ApiMonitorReport
from app.contracts.execution_settings import ExecutionSettings
from app.modules.management.api_usage import build_report
from app.modules.management.api_monitor import build_api_monitor
from app.modules.management.execution_settings import execution_settings
from app.modules.management.api_stats.models import ApiUsageFact
with session_factory()() as session:
    session.execute(text('SET TRANSACTION READ ONLY'))
    user = session.scalar(select(UserRecord).where(UserRecord.status == 'active',
        UserRecord.role == 'super_admin', UserRecord.identity_source != 'development'))
    assert user is not None, 'No authorized production administrator'
    settings = ExecutionSettings.model_validate(execution_settings(user, session))
    assert settings.api.enabled and settings.api.taskConcurrency == 5
    assert settings.api.imagesPerBatch == 10 and settings.api.requestTimeoutSeconds == 180
    assert settings.api.downloadTimeoutSeconds == 60 and settings.api.leaseSeconds == 360
    assert settings.cli.enabled and settings.cli.concurrency == settings.cli.capacity == 5
    assert settings.cli.timeoutSeconds == settings.cli.timeoutCapacity == 7200
    assert not settings.retention.enabled
    assert settings.retention.cacheIdleDays == 1 and settings.retention.historyIdleDays == 7
    monitor = ApiMonitorReport.model_validate(build_api_monitor(session, user))
    channels = {c.channel: c for c in monitor.channels}
    assert set(channels) == {'api', 'cli'}
    for channel in channels.values():
        assert channel.state == channel.queueState == 'available', 'Worker heartbeat not ready'
        assert channel.workers and all(w.state == 'available' and w.capacity == 5 for w in channel.workers)
    report = Report.model_validate(build_report(session, user, UsageQuery()))
    assert report.scope == 'all'
    count = session.scalar(select(func.count()).select_from(ApiUsageFact))
    print(json.dumps(dict(settings=settings.model_dump(), channels={k: dict(state=v.state,
        workers=len(v.workers), queueState=v.queueState) for k,v in channels.items()},
        facts=count, eventCount=report.total, inventory=report.inventory.model_dump())))
'''


def verify_contracts():
    # New independent heartbeat can take a polling interval to arrive.
    for attempt in range(20):
        try:
            return json.loads(subprocess.check_output(['docker', 'exec',
                'hengxin-vps-staging-api-1', 'python', '-c', CONTRACT_CHECK], text=True))
        except subprocess.CalledProcessError:
            if attempt == 19:
                raise
            time.sleep(3)

REQUIRED_PROMPTS = {
    'backend/app/modules/api_image_edits/' + name
    for name in ('image_edit_prompt.txt', 'text_edit_prompt.txt', 'text_repair_prompt.txt')
}


def validate_prompt_manifest(manifest):
    assert REQUIRED_PROMPTS <= manifest['files'].keys(), 'Required prompt missing from manifest'


def validate_release_markers(app, manifest):
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json', 'MANAGEMENT_RELEASE.json'):
        deployed = json.loads((app / name).read_text())
        assert all(deployed[key] == manifest[key] for key in ('release', 'commit', 'migration', 'frontendVersion', 'files')), name


def validate_kind_column(sql):
    assert sql("SELECT is_nullable || ':' || data_type || ':' || character_maximum_length FROM information_schema.columns WHERE table_name='api_image_versions' AND column_name='kind'") == 'YES:character varying:20'


def main():
    release = sys.argv[1]
    assert re.fullmatch(r'management-20261010-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    app = Path('/opt/hengxin-smart-image')
    manifest = json.loads((work / 'src/release.json').read_text())
    assert manifest['release'] == release and manifest['migration'] == '0026'
    assert manifest['frontendVersion'] == '0.2.20'
    assert sys.argv[2:] in ([], ['--installed-only'])
    installed_only = sys.argv[2:] == ['--installed-only']
    validate_prompt_manifest(manifest)
    validate_release_markers(app, manifest)
    old = json.loads((work / 'old-compose.private.json').read_text())
    prefix = 'hengxin-vps-staging-'
    def run(*args, input=None):
        return subprocess.check_output(args, input=input, text=True).strip()
    def sql(q):
        return run('docker','exec',prefix+'postgres-1','psql','-v','ON_ERROR_STOP=1','-U','hengxin','-d','hengxin','-Atc',q)
    result = {'release': release, 'commit': manifest['commit'], 'services': []}
    backend = {n.removeprefix('backend/'): digest for n,digest in manifest['files'].items() if n.startswith('backend/')}
    check_code = 'import sys,json,hashlib; from pathlib import Path; files=json.load(sys.stdin); assert all(hashlib.sha256((Path("/app")/n).read_bytes()).hexdigest()==h for n,h in files.items()); print(len(files))'
    image_id = (work / 'INSTALL_TEST_IMAGE_ID').read_text().strip()
    for name in ('api','outbox','api-image-worker','api-image-outbox','image-variants'):
        live = json.loads(run('docker','inspect',prefix+name+'-1'))[0]
        assert live['State']['Running'] and live['Image'] == image_id, name
        spec = old['services'][name]
        env = dict(v.split('=',1) for v in live['Config']['Env'])
        assert all(env.get(k) == str(v) for k,v in spec.get('environment',{}).items()), name
        assert not spec.get('command') or spec['command'] == live['Config']['Cmd'], name
        count = int(run('docker','exec','-i',prefix+name+'-1','python','-c',check_code,input=json.dumps(backend)))
        result['services'].append({'name':name,'imageMatched':True,'configPreserved':True,'filesMatched':count})
    counts = {'native':0,'frontend':0}
    for name,digest in manifest['files'].items():
        if name.startswith('backend/app/'):
            target, group = app/name, 'native'
        elif name.startswith('frontend/'):
            target, group = app/name, 'frontend'
        elif name in ('infra/nginx.vps.conf', 'infra/nginx.media.conf'):
            assert hashlib.sha256((app/name).read_bytes()).hexdigest() == digest, name
            continue
        else:
            continue
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, name
        counts[group] += 1
    result['hashes'] = counts
    result['schema'] = sql('SELECT version_num FROM alembic_version')
    assert result['schema'] == '0026'
    result['management'] = verify_contracts()
    for column in ('request_width','request_height','return_width','return_height'):
        assert sql("SELECT is_nullable FROM information_schema.columns WHERE table_name='api_image_attempts' AND column_name='" + column + "'") == 'YES'
    validate_kind_column(sql)
    result['operationKindColumn'] = 'nullable varchar(20)'
    result['frontendVersion'] = json.loads((app/'frontend/package.json').read_text())['version']
    assert result['frontendVersion'] == '0.2.20'
    result['native'] = run('systemctl','is-active','hengxin-vps-codex-worker')
    assert result['native'] == 'active'
    assert sql('SELECT paused FROM api_image_channel WHERE id=1') == ('t' if installed_only else 'f')
    assert sql('SELECT enabled FROM capacity_gate WHERE id=1') == 'f'
    result['cliJobs'] = sql('SELECT status,count(*) FROM job_records GROUP BY status ORDER BY status')
    result['apiItems'] = sql('SELECT state,count(*) FROM api_image_items GROUP BY state ORDER BY state')
    result['ready'] = json.loads(run('curl','-fsS','http://127.0.0.1:18008/api/v1/health/ready'))
    if installed_only:
        result['verification'] = 'installed-only'
        print(json.dumps(result, indent=2))
        return
    result['public'] = []
    public = 'https://zhitu.qhhengxin.top'
    with urllib.request.urlopen(public + '/', timeout=30) as response:
        html = response.read()
        assert hashlib.sha256(html).hexdigest() == manifest['files']['frontend/dist/index.html']
        result['public'].append({'path':'/','status':response.status,'hashMatched':True})
    for path in re.findall(r'(?:src|href)="(/assets/[^"?]+\.(?:js|css))"',html.decode()):
        with urllib.request.urlopen(public+path,timeout=30) as response:
            assert hashlib.sha256(response.read()).hexdigest() == manifest['files']['frontend/dist'+path]
            result['public'].append({'path':path,'status':response.status,'hashMatched':True})
    assert len(result['public']) >= 3
    result['anonymousAuthStatus'] = run('curl','-sS','-o','/dev/null','-w','%{http_code}',public+'/api/v1/auth/me')
    assert result['anonymousAuthStatus'] == '401'
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
