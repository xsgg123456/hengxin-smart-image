import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

REQUIRED_PROMPTS = {
    'backend/app/modules/api_image_edits/' + name
    for name in ('image_edit_prompt.txt', 'text_edit_prompt.txt', 'text_repair_prompt.txt')
}


def validate_prompt_manifest(manifest):
    assert REQUIRED_PROMPTS <= manifest['files'].keys(), 'Required prompt missing from manifest'


def validate_release_markers(app, manifest):
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json'):
        deployed = json.loads((app / name).read_text())
        assert all(deployed[key] == manifest[key] for key in ('release', 'commit', 'migration', 'frontendVersion', 'files')), name


def validate_kind_column(sql):
    assert sql("SELECT is_nullable || ':' || data_type || ':' || character_maximum_length FROM information_schema.columns WHERE table_name='api_image_versions' AND column_name='kind'") == 'YES:character varying:20'


def main():
    release = sys.argv[1]
    assert re.fullmatch(r'api-edit-20260930-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    app = Path('/opt/hengxin-smart-image')
    manifest = json.loads((work / 'src/release.json').read_text())
    assert manifest['release'] == release and manifest['migration'] == '0022'
    assert manifest['frontendVersion'] == '0.2.16'
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
        else:
            continue
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, name
        counts[group] += 1
    result['hashes'] = counts
    result['schema'] = sql('SELECT version_num FROM alembic_version')
    assert result['schema'] == '0022'
    for column in ('request_width','request_height','return_width','return_height'):
        assert sql("SELECT is_nullable FROM information_schema.columns WHERE table_name='api_image_attempts' AND column_name='" + column + "'") == 'YES'
    validate_kind_column(sql)
    result['operationKindColumn'] = 'nullable varchar(20)'
    result['frontendVersion'] = json.loads((app/'frontend/package.json').read_text())['version']
    assert result['frontendVersion'] == '0.2.16'
    result['native'] = run('systemctl','is-active','hengxin-vps-codex-worker')
    assert result['native'] == 'active'
    assert sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    assert sql('SELECT enabled FROM capacity_gate WHERE id=1') == 'f'
    result['cliJobs'] = sql('SELECT status,count(*) FROM job_records GROUP BY status ORDER BY status')
    result['apiItems'] = sql('SELECT state,count(*) FROM api_image_items GROUP BY state ORDER BY state')
    result['ready'] = json.loads(run('curl','-fsS','http://127.0.0.1:18008/api/v1/health/ready'))
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
