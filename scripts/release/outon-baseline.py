"""Standalone read-only baseline probe; contains no credentials or production writes."""
import base64
import json
from pathlib import Path
import subprocess

FILES = {'app/overseas/'+name+'.py' for name in (
    'auth/models', 'auth/dependencies', 'auth/router', 'config', 'db', 'permissions', 'members/schemas', 'materials/service',
    'tasks/schemas', 'tasks/requirements', 'tasks/queries', 'tasks/service',
    'studio/recovery_router', 'studio/recovery_files', 'studio/queries', 'studio/message_metadata')} | {
    'migrations/overseas/versions/0024_designer_roles.py'}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45, check=True)
    return result.stdout.strip()


def snapshot():
    api = 'hengxin-overseas-api-1'
    code = ('import base64,json,pathlib;print(json.dumps({n:base64.b64encode(pathlib.Path("/app",n).read_bytes()).decode() '
            'if pathlib.Path("/app",n).is_file() else None for n in '+repr(sorted(FILES))+'}))')
    sources = json.loads(run('docker', 'exec', api, 'python', '-B', '-c', code))
    units = {u:{k:run('systemctl', 'show', u, '-p', k, '--value') for k in
        ('MainPID', 'WorkingDirectory', 'SendSIGKILL', 'TimeoutStopUSec', 'KillMode', 'Restart')} for u in UNITS}
    return dict(image=run('docker', 'inspect', '--format', '{{.Image}}', api), sources=sources, units=units,
        frontendVersion=json.loads(Path('/opt/hengxin-smart-image/frontend/package.json').read_text())['version'])


if __name__ == '__main__':
    print(json.dumps(snapshot()))
