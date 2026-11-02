"""Read-only production evidence. Send this file to python3 over the approved SSH connection."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

API = 'hengxin-overseas-api-1'
FILES = {'app/overseas/db.py', 'app/overseas/tasks/schemas.py'} | {
    'app/overseas/management/' + n + '.py' for n in ('models', 'schemas', 'router', 'skills', 'settings')
} | {'app/overseas/studio/' + n + '.py' for n in ('queries', 'service')} | {
    'migrations/overseas/versions/0023_skill_platforms.py'}


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Read-only probe failed: ' + args[0])
    return result.stdout.strip()


def tree(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file() and not p.is_symlink()
            and '__pycache__' not in p.parts and '.venv' not in p.parts}


def snapshot():
    live = json.loads(run('docker', 'inspect', API))[0]
    code = ('import base64,json,pathlib;print(json.dumps({n:base64.b64encode(pathlib.Path("/app",n).read_bytes()).decode() '
            'if pathlib.Path("/app",n).is_file() else None for n in ' + repr(sorted(FILES)) + '}))')
    sources = json.loads(run('docker', 'exec', API, 'python', '-B', '-c', code))
    containers = {}
    for name in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines():
        row = json.loads(run('docker', 'inspect', name))[0]
        containers[name] = dict(id=row['Id'], image=row['Image'], running=row['State']['Running'])
    units = {}
    rows = run('systemctl', 'list-units', '--type=service', '--state=running', '--no-legend')
    for line in rows.splitlines():
        unit = line.split()[0]
        if 'hengxin' not in unit:
            continue
        pid = int(run('systemctl', 'show', unit, '-p', 'MainPID', '--value'))
        directory = Path('/proc') / str(pid)
        paths = set()
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            paths.update(p for p in run('systemctl', 'show', unit, '-p', key, '--value').split() if p.startswith('/'))
        cwd = Path(os.readlink(directory / 'cwd'))
        units[unit] = dict(pid=pid, cwd=str(cwd), files={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
                           source=tree(cwd / 'app') if (cwd / 'app').is_dir() else {})
    skills = Path('/var/lib/hengxin-overseas/local-skills')
    app = Path('/opt/hengxin-smart-image')
    result = dict(image=live['Image'], apiId=live['Id'], sources=sources, containers=containers, units=units,
                  skills=tree(skills), frontendVersion=json.loads((app/'frontend/package.json').read_text())['version'],
                  frontend={str(p.relative_to(app)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (app/'frontend/package.json', app/'frontend/dist/index.html')})
    return result


if __name__ == '__main__':
    print(json.dumps(snapshot()))
