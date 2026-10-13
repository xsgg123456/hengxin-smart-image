"""Publish the reviewed 14-package collection to one overseas-only directory."""
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/var/lib/hengxin-overseas/local-skills')
OLD_VOLUME = '/var/lib/docker/volumes/hengxin-overseas_overseas_local_skills/_data'
ENVIRONMENT = Path('/etc/hengxin-overseas/worker.env')
RELEASE = '7f409fdc92401c25f559899e3529720480b482cee0bfbbbca8daaecb0c0c2bbc'


def environment():
    values = {}
    for line in ENVIRONMENT.read_text().splitlines():
        if line and not line.startswith('#'):
            key, raw = line.split('=', 1)
            parts = shlex.split(raw)
            assert len(parts) <= 1, 'Invalid native environment value'
            values[key] = parts[0] if parts else ''
    assert values.get('OVERSEAS_APP_ENV') == 'production'
    assert values.get('OVERSEAS_LOCAL_SKILL_ROOT') == str(ROOT)
    return {**{k: v for k, v in os.environ.items() if k in ('PATH', 'LANG')},
            **values, 'HX_BUSINESS_CONTEXT': 'overseas', 'PYTHONDONTWRITEBYTECODE': '1'}


def invoke(target, arguments, *, worker=False):
    import pwd
    person = pwd.getpwnam('hengxin-overseas')
    def demote():
        os.setgroups([])
        os.setgid(person.pw_gid)
        os.setuid(person.pw_uid)
    result = subprocess.run([str(target / '.venv/bin/python'), *arguments], cwd=target,
        env=environment(), preexec_fn=demote if worker else None,
        capture_output=True, text=True, timeout=240)
    if result.returncode:
        # Do not expose configuration or provider credentials through subprocess output.
        raise RuntimeError('Overseas Skill installation/read probe failed; inspect private runtime')
    return json.loads(result.stdout)


def bundle(work):
    return work / 'skills' / RELEASE


def overlay():
    # Compose merges mounts by container destination; replace only local-skills.
    return dict(type='bind', source=str(ROOT), target=str(ROOT), read_only=True,
                bind={'create_host_path': False})


def preflight(r, work, target):
    environment()
    assert ROOT.is_dir() and not ROOT.is_symlink()
    assert all(not p.is_symlink() for p in ROOT.parents)
    live = json.loads(r.run('docker', 'inspect', r.API, capture=True))[0]
    mount = [m for m in live['Mounts'] if m['Destination'] == str(ROOT)]
    assert len(mount) == 1 and mount[0]['Source'] in (OLD_VOLUME, str(ROOT))
    if mount[0]['Source'] == OLD_VOLUME:
        # Do not silently abandon a pre-existing separate collection.
        assert not any(Path(OLD_VOLUME).iterdir()), 'Old API Skill volume is not empty'
        assert not any(ROOT.iterdir()), 'Native Skill root is not empty'
    code = ('from app.overseas.management.skill_install import verify_bundle, summary; '
        'from app.overseas.management.installed_tree import digest; import sys,json; '
        'm=verify_bundle(sys.argv[1]); print(json.dumps(summary(digest(m),m["items"])))')
    result = invoke(target, ['-c', code, str(bundle(work))])
    assert result['release'] == RELEASE and result['packages'] == 14 and result['files'] == 181
    r.private(work / 'SKILLS_PREFLIGHT.json', result)


def install(r, work, target, backup):
    assert os.geteuid() == 0 and ROOT.is_dir() and not ROOT.is_symlink()
    assert all(not p.is_symlink() for p in ROOT.parents)
    info = ROOT.stat()
    r.private(backup / 'skill-root-before.json', dict(path=str(ROOT), uid=info.st_uid,
        gid=info.st_gid, mode=info.st_mode & 0o777))
    # Exact confirmed directory only; package contents are published by the validated installer.
    os.chown(ROOT, 0, 0)
    ROOT.chmod(0o755)
    releases = ROOT / 'releases'
    releases.mkdir(exist_ok=True, mode=0o755)
    assert releases.is_dir() and not releases.is_symlink() and releases.stat().st_uid == 0
    # The deployer's umask is 077; workers must still traverse this public catalog.
    releases.chmod(0o755)
    result = invoke(target, ['-m', 'app.overseas.management.skill_install', 'install',
                             '--bundle', str(bundle(work))])
    assert result['release'] == RELEASE and result['packages'] == 14 and result['files'] == 181
    r.private(work / 'SKILLS_INSTALLED.json', result)


def verify(r, work, target):
    native = invoke(target, ['-m', 'app.overseas.management.skill_install', 'verify'], worker=True)
    sandbox = invoke(target, ['-m', 'app.overseas.management.skill_probe'], worker=True)
    api = json.loads(r.run('docker', 'exec', r.API, 'python', '-m',
        'app.overseas.management.skill_install', 'verify', capture=True))
    live = json.loads(r.run('docker', 'inspect', r.API, capture=True))[0]
    mount = [m for m in live['Mounts'] if m['Destination'] == str(ROOT)]
    assert len(mount) == 1 and mount[0]['Source'] == str(ROOT) and mount[0]['RW'] is False
    for result in (native, sandbox, api):
        assert result['release'] == RELEASE and result['packages'] == 14 and result['files'] == 181
    assert native['directoryIdentity'] == api['directoryIdentity'] == sandbox['directoryIdentity']
    assert sandbox['uid'] != 0 and all(row['readOnly'] for row in sandbox['results'])
    r.private(work / 'SKILLS_VERIFIED.json', dict(native=native, api=api, sandbox=sandbox,
                                               modelCalls=0, sharedDirectory=True))
