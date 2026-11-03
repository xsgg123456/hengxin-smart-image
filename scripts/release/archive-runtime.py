"""Frontend-only archive release identity, package checks and read-only host probes."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.request

VERSION, BASE_VERSION = '0.2.62', '0.2.61'
BASE_IMAGE = 'sha256:44376948ece1f3ed50fb99c8ebc7ef7fdfdbad486b714c3987c2c64c793f9067'
APP = Path('/opt/hengxin-smart-image')
HELPERS = ('archive-runtime', 'archive-deploy')
ENTRIES = ('frontend/dist/index.html.gz', 'frontend/dist/index.html', 'frontend/package.json', 'FRONTEND_RELEASE.json')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def helper(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(path):
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked release path')


def private(path, value):
    safe(path)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2))
    path.chmod(0o600)


def entry_refs(index):
    require('overseas-preview' not in index, 'Preview is not production')
    refs = re.findall(r'(?:src|href)=["\']/?(assets/[^"\'?#]+)', index)
    require(any(ref.endswith('.js') for ref in refs), 'Missing production JavaScript')
    return refs


def verify_frontend(files):
    index = files['frontend/dist/index.html']
    require(all('frontend/dist/'+ref in files for ref in entry_refs(index.decode())), 'Missing entry asset')
    if 'frontend/dist/index.html.gz' in files:
        require(gzip.decompress(files['frontend/dist/index.html.gz']) == index, 'Compressed entry mismatch')


def verify_package(source):
    safe(source)
    manifest = json.loads((source/'release.json').read_text())
    require(manifest.get('version') == VERSION and manifest.get('baseVersion') == BASE_VERSION and
            manifest.get('baseImage') == BASE_IMAGE and manifest.get('frontendOnly') is True, 'Unexpected release scope')
    require(manifest.get('mode') == 'release', 'Only approved committed release packages can deploy')
    require(re.fullmatch('[a-f0-9]{40}', manifest.get('commit', '')) and
            re.fullmatch('[a-f0-9]{64}', manifest.get('candidateId', '')), 'Missing reviewed source identity')
    require(manifest.get('release') == 'archive-20261103-'+manifest['commit'][:7], 'Unexpected release name')
    files = manifest['files']
    required = {'scripts/release/'+n+'.py' for n in HELPERS} | {'frontend/package.json','frontend/dist/index.html'}
    require(required <= files.keys(), 'Incomplete package')
    for name, expected in files.items():
        parts = PurePosixPath(name).parts
        require('\\' not in name and not name.startswith('/') and '..' not in parts and
                (name in required or name.startswith('frontend/dist/')), 'Unexpected package path')
        path = source/name
        safe(path)
        require(path.resolve().is_relative_to(source.resolve()) and digest(path) == expected, 'Package checksum mismatch: '+name)
    actual = list(source.rglob('*'))
    require(not any(p.is_symlink() for p in actual), 'Linked package content')
    require({p.relative_to(source).as_posix() for p in actual if p.is_file()} == set(files)|{'release.json'}, 'Unmanifested content')
    require(json.loads((source/'frontend/package.json').read_text())['version'] == VERSION, 'Version mismatch')
    verify_frontend({name:(source/name).read_bytes() for name in files if name.startswith('frontend/dist/')})
    return manifest


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    require(result.returncode == 0, 'Host probe failed; inspect host privately')
    return result.stdout.strip()


def baseline(app):
    live = json.loads(run('docker','inspect','hengxin-overseas-api-1'))[0]
    require(live['State']['Running'] and live['Image'] == BASE_IMAGE, 'Backend baseline drift')
    units = ('hengxin-overseas-worker.service','hengxin-overseas-outbox.service')
    services = {u:run('systemctl','show',u,'-p','MainPID','-p','ActiveState','-p','ExecMainStartTimestampMonotonic') for u in units}
    require(all('ActiveState=active' in s and 'MainPID=0' not in s.splitlines() for s in services.values()), 'Native service not active')
    revision = run('docker','exec','hengxin-overseas-overseas-postgres-1','psql','-v','ON_ERROR_STOP=1',
                   '-U','postgres','-d','hengxin_overseas','-Atc','SELECT version_num FROM overseas_alembic_version')
    require(revision == 'overseas_0026', 'Schema baseline drift')
    return dict(image=live['Image'], container=live['Id'], startedAt=live['State']['StartedAt'], services=services,
                revision=revision, config={p.relative_to(app).as_posix():digest(p) for p in (app/'infra').glob('*')
                                         if p.is_file() and p.suffix in ('.yaml','.conf','.env')})


def installed(source, app):
    manifest = verify_package(source)
    for name, expected in manifest['files'].items():
        if name.startswith('frontend/'):
            safe(app/name)
            require(digest(app/name) == expected, 'Installed frontend checksum mismatch')
    require(digest(app/'FRONTEND_RELEASE.json') == digest(source/'release.json'), 'Installed manifest mismatch')
    # Requests traverse the real gateway and its runtime identity from the final install path.
    refs = ['index.html', *entry_refs((source/'frontend/dist/index.html').read_text())]
    for ref in refs:
        request = urllib.request.Request('https://zhitu.qhhengxin.top/'+ref, headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'})
        with urllib.request.urlopen(request, timeout=30) as response:
            require(response.status == 200 and hashlib.sha256(response.read()).hexdigest() ==
                    digest(source/'frontend/dist'/ref), 'Live static bytes mismatch: '+ref)
    for url in ('http://127.0.0.1:18018/api/overseas/v1/health/ready','http://127.0.0.1:18080/api/v1/health/ready'):
        with urllib.request.urlopen(url, timeout=10) as response:
            require(response.status == 200, 'Readiness failure')
    return dict(version=VERSION, checkedHttpAssets=len(refs), installedHashes='PASS')
