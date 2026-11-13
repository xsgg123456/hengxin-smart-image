"""Small LAN adapters for backups, static compatibility and web-only switching."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from snapshot import database, sha


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def keep_assets(u, previous, candidate):
    """Retain the prior build's assets, without recursively carrying older builds."""
    path = candidate / 'release-manifest.json'
    m = json.loads(path.read_bytes())
    m.setdefault('frontend_current_files', {n: h for n, h in m['files'].items() if n.startswith('frontend/')})
    compatibility = m.setdefault('compatibility_files', {})
    prior = json.loads((previous / 'release-manifest.json').read_bytes())
    prior_files = prior.get('frontend_current_files', {
        n: h for n, h in prior['files'].items() if n not in prior.get('compatibility_files', {})})
    folder = previous / 'frontend/assets'
    if folder.exists():
        for source in folder.rglob('*'):
            u.safe(source)
            if not source.is_file():
                continue
            name = source.relative_to(previous).as_posix()
            if name not in prior_files:
                continue
            target = candidate / name
            digest = sha(source.read_bytes())
            if digest != prior_files[name]:
                raise RuntimeError('Previous frontend asset differs from manifest: ' + name)
            if target.exists():
                if sha(target.read_bytes()) != digest:
                    raise RuntimeError('Static asset filename collision: ' + name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            u.safe(target, missing=True)
            shutil.copyfile(source, target)
            target.chmod(0o644)
            m['files'][name] = compatibility[name] = digest
    u.write(path, (json.dumps(m, indent=2) + '\n').encode(), mode=0o644)


def backup(u, work, scope=None, pass_fds=()):
    folder = work / 'data-backup'
    if folder.exists():
        raise RuntimeError('Backup directory already exists; inspect transaction')
    folder.mkdir(mode=0o700)
    report = {}
    inherit = {'pass_fds': pass_fds} if pass_fds else {}
    for side in (('domestic', 'overseas') if scope is None else () if scope == 'shared' else (scope,)):
        name, user, db = database(u, side)
        path = folder / (side + '.dump')
        with path.open('xb') as stream:
            os.chmod(path, 0o600)
            result = subprocess.run(['docker', 'exec', name, 'pg_dump', '-U', user, '-d', db, '-Fc'],
                                    stdout=stream, stderr=subprocess.PIPE, timeout=300, **inherit)
        if result.returncode:
            raise RuntimeError('Database backup failed: ' + side)
        with path.open('rb') as stream:
            result = subprocess.run(['docker', 'exec', '-i', name, 'pg_restore', '--list'],
                                    stdin=stream, capture_output=True, timeout=120, **inherit)
        if result.returncode:
            raise RuntimeError('Database backup verification failed: ' + side)
        report[side] = {'bytes': path.stat().st_size, 'sha256': file_sha(path)}
    if scope in (None, 'shared'):
        path = folder / 'accounts-config.tar'
        with path.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            with tarfile.open(fileobj=stream, mode='w') as archive:
                for name in ('/home/codex/account-management', '/home/codex/auth', '/etc/hengxin-lan'):
                    archive.add(name, arcname=name.lstrip('/'))
        report['accounts_config'] = file_sha(path)
    u.write(folder / 'verified.json', json.dumps(report).encode(), exclusive=True)


def prepare_web(u):
    u.validate_release()
    if u.WORK.exists():
        raise RuntimeError('Transaction directory already exists')
    u.WORK.mkdir(mode=0o700)
    original = u.COMPOSE.read_bytes()
    candidate = json.loads(original)
    matches = [v for v in candidate['services']['domestic-web']['volumes']
               if v['target'] == '/usr/share/nginx/html' and v.get('read_only')]
    if len(matches) != 1:
        raise RuntimeError('Unexpected web mount')
    matches[0]['source'] = str(u.RELEASE / 'frontend')
    u.write(u.WORK / 'web-before.json', original, exclusive=True)
    data = (json.dumps(candidate, indent=2) + '\n').encode()
    u.write(u.WORK / 'compose.candidate.json', data, exclusive=True)
    u.compose('config', '--quiet', config=u.WORK / 'compose.candidate.json')
    u.write(u.WORK / 'web-prepared.json', json.dumps({
        'before': sha(original), 'candidate': sha(data), 'manifest': u.validate_release()
    }).encode(), exclusive=True)


def web_guard(u):
    m = json.loads((u.WORK / 'web-prepared.json').read_bytes())
    for filename, key in (('web-before.json', 'before'), ('compose.candidate.json', 'candidate')):
        u.safe(u.WORK / filename)
        if sha((u.WORK / filename).read_bytes()) != m[key]:
            raise RuntimeError('Web transaction backup drift')
    if sha(u.COMPOSE.read_bytes()) not in (m['before'], m['candidate']):
        raise RuntimeError('Concurrent compose change')
    return m


def recover_web(u):
    if (u.WORK / 'rolled-back.json').exists():
        return
    web_guard(u)
    u.write(u.COMPOSE, (u.WORK / 'web-before.json').read_bytes())
    u.app_command('up', ('domestic-web',))
    u.write(u.WORK / 'rolled-back.json', b'{}', exclusive=True)


def apply_web(u):
    if (u.WORK / 'applied.json').exists():
        return
    if (u.WORK / 'started.json').exists():
        raise RuntimeError('Interrupted web release; use recover')
    m = web_guard(u)
    if sha(u.COMPOSE.read_bytes()) != m['before'] or u.validate_release() != m['manifest']:
        raise RuntimeError('Web candidate/configuration drift')
    u.write(u.WORK / 'started.json', b'{}', exclusive=True)
    try:
        u.write(u.COMPOSE, (u.WORK / 'compose.candidate.json').read_bytes())
        u.app_command('up', ('domestic-web',))
        u.write(u.WORK / 'applied.json', b'{}', exclusive=True)
    except BaseException:
        recover_web(u)
        raise
