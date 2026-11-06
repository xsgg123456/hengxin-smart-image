"""Read-only source/identity baseline; never capture environments or user data."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess


FILES = {'app/overseas/management/'+name+'.py' for name in (
    'installed_catalog', 'skill_objects', 'skill_downloads', 'skill_publication', 'skill_cleanup',
    'skill_references', 'skill_publisher', 'skill_install', 'skill_maintenance',
    'skill_transfer_schema', 'skill_probe', 'skill_preparation', 'skill_transfer_store')} | {
    'app/overseas/execution/'+name+'.py' for name in ('materials', 'skill_content', 'skill_cache', 'skill_history')}
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
CONTAINERS = {'api': 'hengxin-overseas-api-1', 'publisher': 'hengxin-skill-publisher'}


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Read-only probe failed: '+args[0])
    return result.stdout.strip()


def code_sources(root):
    result = {}
    for name in sorted(FILES):
        path = root/name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise RuntimeError('Linked source rejected: '+name)
        if not path.exists():
            result[name] = None
        elif not stat.S_ISREG(path.stat().st_mode):
            raise RuntimeError('Non-regular source rejected: '+name)
        else:
            result[name] = base64.b64encode(path.read_bytes()).decode()
    return result


def container_sources(name):
    # Allowlist only Python source; no inspect Config.Env or /proc environ leaves this process.
    code = ('import base64,json,pathlib,stat; names='+repr(sorted(FILES))+'; result={}\n'
        'for name in names:\n'
        ' p=pathlib.Path("/app",name)\n'
        ' if any(q.is_symlink() for q in (p,*p.parents)): raise RuntimeError("Linked source")\n'
        ' if p.exists() and not stat.S_ISREG(p.stat().st_mode): raise RuntimeError("Non-regular source")\n'
        ' result[name]=base64.b64encode(p.read_bytes()).decode() if p.exists() else None\n'
        'print(json.dumps(result))')
    return json.loads(run('docker', 'exec', name, 'python', '-B', '-c', code))


def native_identity(unit):
    pid = int(run('systemctl', 'show', unit, '-p', 'MainPID', '--value'))
    if pid <= 0:
        raise RuntimeError('Native service is not running: '+unit)
    root = Path(os.readlink(Path('/proc')/str(pid)/'cwd'))
    status = (Path('/proc')/str(pid)/'status').read_text()
    values = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    return dict(pid=pid, cwd=str(root), WorkingDirectory=str(root),
                uid=int(values['Uid'].split()[1]), gid=int(values['Gid'].split()[1]))


def snapshot():
    containers, sources = {}, {}
    for role, name in CONTAINERS.items():
        live = json.loads(run('docker', 'inspect', name))[0]
        if not live['State']['Running']:
            raise RuntimeError('Container not running: '+name)
        containers[role] = dict(id=live['Id'], image=live['Image'], startedAt=live['State']['StartedAt'],
            user=live['Config']['User'], mounts=[{k: m.get(k) for k in ('Type', 'Source', 'Destination', 'RW')}
                                                for m in live['Mounts']])
        sources[role] = container_sources(name)
    units = {unit: native_identity(unit) for unit in UNITS}
    native = {unit: code_sources(Path(value['cwd'])) for unit, value in units.items()}
    revision = run('docker', 'exec', 'hengxin-overseas-overseas-postgres-1', 'psql', '-U', 'postgres',
                   '-d', 'hengxin_overseas', '-Atc', 'SELECT version_num FROM overseas_alembic_version')
    version_path = Path('/opt/hengxin-smart-image/frontend/package.json')
    version_bytes = version_path.read_bytes()
    for role, name in CONTAINERS.items():
        live = json.loads(run('docker', 'inspect', name))[0]
        saved = containers[role]
        if (live['Id'], live['Image'], live['State']['StartedAt'], live['State']['Running']) != (
                saved['id'], saved['image'], saved['startedAt'], True) or container_sources(name) != sources[role]:
            raise RuntimeError('Container changed during capture: '+role)
    for unit, saved in units.items():
        if native_identity(unit) != saved or code_sources(Path(saved['cwd'])) != native[unit]:
            raise RuntimeError('Native changed during capture: '+unit)
    if version_path.read_bytes() != version_bytes:
        raise RuntimeError('Frontend changed during capture')
    return dict(kind='skill-physical-baseline', capturedAt=datetime.now(timezone.utc).isoformat(),
        image=containers['api']['image'], apiId=containers['api']['id'], sources=sources['api'],
        publisherImage=containers['publisher']['image'], publisherId=containers['publisher']['id'],
        publisherSources=sources['publisher'], containers=containers,
        mounts=containers['api']['mounts'], publisherMounts=containers['publisher']['mounts'],
        units=units, nativeSources=native, revision=revision,
        frontendVersion=json.loads(version_bytes)['version'])


if __name__ == '__main__':
    print(json.dumps(snapshot()))
