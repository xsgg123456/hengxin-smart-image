"""Read-only standalone polling baseline probe, safe to execute via SSH stdin."""
import base64
import json
from pathlib import Path
import subprocess

FILES = {'app/overseas/drafts/router.py', 'app/overseas/drafts/read.py'}


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Read-only baseline failed: '+args[0])
    return result.stdout.strip()


def snapshot():
    api = 'hengxin-overseas-api-1'
    live = json.loads(run('docker', 'inspect', api))[0]
    if not live['State']['Running']:
        raise RuntimeError('API not running')
    code = ('import base64,json,pathlib;print(json.dumps({n:base64.b64encode(pathlib.Path("/app",n).read_bytes()).decode() '
            'if pathlib.Path("/app",n).is_file() else None for n in '+repr(sorted(FILES))+'}))')
    sources = json.loads(run('docker', 'exec', api, 'python', '-B', '-c', code))
    revision = run('docker', 'exec', 'hengxin-overseas-overseas-postgres-1', 'psql', '-U', 'postgres',
                   '-d', 'hengxin_overseas', '-Atc', 'SELECT version_num FROM overseas_alembic_version')
    if run('docker', 'inspect', '--format', '{{.Id}}', api) != live['Id']:
        raise RuntimeError('API changed during probe')
    return dict(image=live['Image'], apiId=live['Id'], sources=sources, revision=revision,
                frontendVersion=json.loads(Path('/opt/hengxin-smart-image/frontend/package.json').read_text())['version'])


if __name__ == '__main__':
    print(json.dumps(snapshot()))
