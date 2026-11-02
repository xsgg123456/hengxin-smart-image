"""Standalone read-only baseline probe; contains no credentials or production writes."""
import base64
import json
import os
from pathlib import Path
import subprocess

FILES = {'app/overseas/'+name+'.py' for name in (
    'auth/models', 'auth/dependencies', 'auth/router', 'config', 'db', 'permissions', 'members/schemas', 'materials/service',
    'management/models', 'management/skills',
    'tasks/schemas', 'tasks/requirements', 'tasks/queries', 'tasks/service',
    'studio/recovery_router', 'studio/recovery_files', 'studio/queries', 'studio/message_metadata')} | {
    'migrations/overseas/versions/0024_designer_roles.py'}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
NATIVE_FILES = {name for name in FILES if name.startswith('app/')}


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
    native_sources = {}
    for unit, saved in units.items():
        if int(saved['MainPID']) <= 0:
            raise RuntimeError('Native unit is not running: '+unit)
        root = Path(os.readlink(Path('/proc')/saved['MainPID']/'cwd'))
        if str(root) != saved['WorkingDirectory']:
            raise RuntimeError('Native working directory differs: '+unit)
        native_sources[unit] = {}
        for name in sorted(NATIVE_FILES):
            path = root/name
            if any(p.is_symlink() for p in (path, *path.parents)) or (path.exists() and not path.is_file()):
                raise RuntimeError('Unsafe native source: '+name)
            native_sources[unit][name] = base64.b64encode(path.read_bytes()).decode() if path.is_file() else None
        if run('systemctl', 'show', unit, '-p', 'MainPID', '--value') != saved['MainPID']:
            raise RuntimeError('Native process changed during capture: '+unit)
    return dict(image=run('docker', 'inspect', '--format', '{{.Image}}', api), sources=sources, units=units,
        nativeSources=native_sources,
        frontendVersion=json.loads(Path('/opt/hengxin-smart-image/frontend/package.json').read_text())['version'])


if __name__ == '__main__':
    print(json.dumps(snapshot()))
