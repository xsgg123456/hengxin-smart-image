"""Prepare pinned domestic overlay and native services without touching other runtimes."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
r = m.r
UNIT = 'hengxin-vps-codex-worker'
DELETE_UNIT = 'hengxin-domestic-deletions'
DROPIN = Path('/etc/systemd/system/' + UNIT + '.service.d/99-domestic-release.conf')
DELETE_PATH = Path('/etc/systemd/system/' + DELETE_UNIT + '.service')


def validate(work, release):
    assert re.fullmatch(r'domestic-20261015-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.37'
    assert manifest['migration'] == '0029' and manifest['overseasMigration'] == 'overseas_0016'
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def native_policy():
    get = lambda key: m.run('systemctl', 'show', UNIT, '-p', key, '--value', capture=True)
    assert get('User') == 'codex' and get('UMask') == '0077'
    assert get('KillMode') == 'control-group'
    envfiles = [p for p in get('EnvironmentFiles').split() if p.startswith('/')]
    assert envfiles == ['/etc/hengxin-smart-image/worker.env',
                        '/opt/hengxin-releases/codex-astra-20261014/runtime.env'], 'Native environment-file drift'
    assert all(Path(p).is_file() for p in envfiles)
    r.base.native_policy()  # Also verifies live retention disabled, concurrency and timeout.
    root = Path('/opt/hengxin-smart-image/infra/runtime/execution')
    assert root.stat().st_uid == 1001 and root.stat().st_gid == 1001
    assert root.stat().st_mode & 0o777 == 0o700
    pid = int(get('MainPID'))
    env = dict(part.split(b'=', 1) for part in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if part)
    assert env.get(b'CODEX_EXECUTION_ROOT') == str(root).encode(), 'Native execution root drift'
    return dict(environmentFiles=envfiles, limits={key: get(key) for key in ('MemoryMax', 'TasksMax')})


def render_deletion(source, target, policy):
    template = (source / 'infra/hengxin-domestic-deletions.service').read_text()
    assert str(target).startswith('/opt/hengxin-native-releases/domestic-') and '\n' not in str(target)
    return template.replace('@BACKEND@', str(target)).replace('@ENVIRONMENT_FILES@',
        '\n'.join('EnvironmentFile=' + p for p in policy['environmentFiles'])).replace('@LIMITS@',
        '\n'.join(k + '=' + v for k, v in policy['limits'].items() if v))


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    assert r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0016'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.36'
    assert not DROPIN.exists() and not DELETE_PATH.exists(), 'Domestic release already installed'
    m.assets_safe(source)
    data = m.topology()
    policy = native_policy()
    m.private(work / 'topology.json', data)
    m.private(work / 'native-policy.json', policy)
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    names = [*r.SERVICES, 'migrate']
    overlay = work / 'domestic-overlay.json'
    m.private(overlay, {'services': {name: {'image': identity, 'build': {
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}} for name in names}})
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', overlay=overlay, capture=True))
    m.same_settings(old, new, names)
    m.private(work / 'domestic-compose.private.json', old)
    previous = Path(data['native'][UNIT])
    same_dependencies = all((source / 'backend' / n).read_bytes() == (previous / n).read_bytes()
                            for n in ('pyproject.toml', 'uv.lock'))
    target = (m.prepare_domestic_native(source, manifest['release'], previous) if same_dependencies
              else r.prepare_native(source, manifest['release']))
    m.private(work / 'native-target', str(target))
    m.private(work / (DELETE_UNIT + '.service'), render_deletion(source, target, policy))
    m.run('systemd-analyze', 'verify', str(work / (DELETE_UNIT + '.service')))
    # Verify installed argument wiring before any unit or intake changes.
    help_text = m.run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'), '-m',
                     'app.retention.worker', '--help', cwd=target, capture=True)
    assert all(flag in help_text for flag in ('--deletions-only', '--loop', '--interval'))
    m.module('domestic-gate').save(work)
    assert m.topology() == data, 'Topology drift during preparation'
    m.private(work / 'PREPARED', identity)


def unchanged_other_groups(data):
    for group in ('identity', 'overseas'):
        for name, identity in data[group]['ids'].items():
            live = m.live(name)
            assert live['Id'] == identity and live['State']['Running'], 'Unrelated service changed'
    for unit, directory in data['native'].items():
        if unit != UNIT:
            assert m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True) == directory
            m.run('systemctl', 'is-active', unit, capture=True)


def switch_native(work):
    target = Path((work / 'native-target').read_text())
    m.private(DROPIN, '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' +
        str(target / '.venv/bin/celery') + ' -A app.worker.celery_app:celery_app worker --pool=prefork '
        '--concurrency=5 --loglevel=INFO --hostname=hx-vps-codex@%H\n')
    shutil.copyfile(work / (DELETE_UNIT + '.service'), DELETE_PATH)
    DELETE_PATH.chmod(0o644)
    m.run('systemctl', 'daemon-reload')
    m.run('systemctl', 'start', UNIT)


def verify_deletions(work):
    m.run('systemctl', 'is-active', DELETE_UNIT, capture=True)
    pid = int(m.run('systemctl', 'show', DELETE_UNIT, '-p', 'MainPID', '--value', capture=True))
    assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == Path((work / 'native-target').read_text())
    argv = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    assert b'app.retention.worker' in argv and b'--deletions-only' in argv and b'--loop' in argv
    assert argv[argv.index(b'--interval') + 1] == b'5'
    env = dict(part.split(b'=', 1) for part in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if part)
    assert env.get(b'CLI_RETENTION_ENABLED') == b'false'
    assert Path(f'/proc/{pid}').stat().st_uid == 1001
