"""Install isolated services without touching domestic runtime data."""
import json
import os
from pathlib import Path
import pwd
import shutil
import shlex
import subprocess
import socket
import time


def setup(r, work, source, image):
    topology = r.module('overseas-topology')
    domestic = dict(v.split('=', 1) for v in r.inspect('api')['Config']['Env'])
    pid = r.run('systemctl', 'show', 'hengxin-vps-codex-worker', '-p', 'MainPID', '--value', capture=True)
    native = dict(os.fsdecode(v).split('=', 1) for v in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if v)
    for key in ('CODEX_BINARY', 'CODEX_BWRAP_BINARY', 'CODEX_VERSION'):
        domestic[key] = native[key]
    for port in (18018, 18012, 15443, 16398, 15910):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    data = topology.prepare(work, source, image, domestic)
    r.private(work / 'topology-paths.json', {k: str(v) if isinstance(v, Path) else v for k, v in data.items()})
    return data, native


def compose_command(data, business):
    return ['docker', 'compose', '--env-file', str(data[business + '_env']), '-f',
            str(data[business + '_compose']), '-f', str(data[business + '_overlay'])]


def start_resources(r, data):
    for name in ('hx-identity-domestic', 'hx-identity-overseas', 'hx-overseas-edge'):
        if subprocess.run(['docker', 'network', 'inspect', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            r.run('docker', 'network', 'create', '--internal', name)
    for business in ('identity', 'overseas'):
        r.run(*compose_command(data, business), 'config', '--quiet')
        r.run(*compose_command(data, business), 'up', '-d', '--wait', '--wait-timeout', '180')
    r.run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18018/api/overseas/v1/health/ready')
    r.run('curl', '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18012/api/identity/v1/config')


def install_executor(r, work, source, native):
    account = 'hengxin-overseas'
    try:
        person = pwd.getpwnam(account)
    except KeyError:
        r.run('useradd', '--system', '--home-dir', '/var/lib/hengxin-overseas', '--shell', '/usr/sbin/nologin', account)
        person = pwd.getpwnam(account)
    target = Path('/opt/hengxin-overseas/backend')
    assert not target.exists(), 'Existing overseas native installation needs an upgrade plan'
    target.parent.mkdir(mode=0o755, exist_ok=True)
    target.parent.chmod(0o755)
    shutil.copytree(source / 'backend', target)
    for p in (target, *target.rglob('*')):
        p.chmod(0o755 if p.is_dir() else 0o644)
    r.run('uv', 'sync', '--locked', '--no-install-project', '--no-dev', '--python', '/opt/hengxin-smart-image/backend/.venv/bin/python', cwd=target, preexec_fn=lambda: os.umask(0o022))
    r.run('uv', 'pip', 'check', '--python', str(target / '.venv/bin/python'))
    r.run('runuser', '-u', account, '--', str(target / '.venv/bin/python'), '-c',
          'import celery,app; print("OVERSEAS_NATIVE_IMPORT_PASS")', cwd=target)
    for name in ('', 'auth', 'execution', 'skills', 'local-skills'):
        directory = Path('/var/lib/hengxin-overseas') / name
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        os.chown(directory, person.pw_uid, person.pw_gid)
    auth = Path('/var/lib/hengxin-overseas/auth/auth.json')
    assert not auth.exists()
    shutil.copyfile(native['CODEX_AUTH_FILE'], auth)
    auth.chmod(0o600)
    os.chown(auth, person.pw_uid, person.pw_gid)
    config = Path('/etc/hengxin-overseas')
    config.mkdir(mode=0o700, exist_ok=True)
    shutil.copyfile(work / 'worker.env', config / 'worker.env')
    (config / 'worker.env').chmod(0o600)
    for name in ('worker', 'outbox'):
        unit = f'hengxin-overseas-{name}.service'
        dest = Path('/etc/systemd/system') / unit
        assert not dest.exists(), 'Existing overseas unit must not be overwritten'
        shutil.copy2(source / 'infra' / unit, dest)
        drop = dest.with_name(unit + '.d')
        drop.mkdir(exist_ok=True)
        (drop / '50-resources.conf').write_text('[Service]\nMemoryMax=' + ('2G' if name == 'worker' else '256M') + '\nCPUQuota=' + ('200%' if name == 'worker' else '50%') + '\n')
    r.run('systemctl', 'daemon-reload')
    # No paid calls: installed sandbox and binary smoke test only.
    probe = '''from uuid import uuid4
import subprocess
from app.core.config import get_settings
from app.execution.workspace import prepare_workspace,sandbox_command
s=get_settings(); w=prepare_workspace(s.codex_execution_root,uuid4(),uuid4(),s.codex_auth_file)
print(subprocess.check_output(sandbox_command(w,s.codex_binary,['--version'],s.codex_bwrap_binary),text=True).strip())
'''
    worker_env = {k: shlex.split(v)[0] for line in (config / 'worker.env').read_text().splitlines()
                  if line and not line.startswith('#') for k,v in [line.split('=', 1)]}
    worker_env['HX_BUSINESS_CONTEXT'] = 'overseas'
    def demote():
        os.setgroups([])
        os.setgid(person.pw_gid)
        os.setuid(person.pw_uid)
    subprocess.run([str(target / '.venv/bin/python'), '-c', probe], cwd=target,
                   env={**os.environ, **worker_env}, preexec_fn=demote, check=True, timeout=30)
    r.run('systemctl', 'enable', '--now', 'hengxin-overseas-worker', 'hengxin-overseas-outbox')
    for name in ('worker', 'outbox'):
        r.run('systemctl', 'is-active', 'hengxin-overseas-' + name)
    time.sleep(3)


def admin_candidate(r, work):
    query = "SELECT json_agg(t) FROM (SELECT u.name,i.corp_id,i.provider_user_id FROM users u JOIN user_identities i ON i.user_id=u.id WHERE u.name='张帅' AND u.status='active' AND i.provider='dingtalk') t"
    records = json.loads(r.sql(query) or '[]')
    assert len(records) == 1, 'Administrator identity is ambiguous or absent'
    r.private(work / 'administrator.private.json', records[0])
    # No row or login credential is fabricated. Explicit bootstrap follows verified registration.
    print('ADMIN_CANDIDATE_VERIFIED_DOMESTIC_PENDING_UNIFIED_LOGIN', flush=True)
