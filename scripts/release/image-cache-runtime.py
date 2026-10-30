"""Overseas-only image patch; retain actual production Compose and worker identities."""
import importlib.util
import json
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('account_runtime', Path(__file__).with_name('account-runtime.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
run, require, digest, private = a.run, a.require, a.digest, a.private
API = 'hengxin-overseas-api-1'
UNITS = ('hengxin-overseas-worker.service', 'hengxin-overseas-outbox.service')
ENV = {'OVERSEAS_CODEX_TIMEOUT_SECONDS': '7200', 'OVERSEAS_QUEUE_VISIBILITY_SECONDS': '7800'}
FILES = {'app/overseas/' + name for name in (
    'attachment_delivery.py', 'config.py', 'studio/files.py', 'studio/router.py',
    'materials/files.py', 'materials/router.py', 'archives/service.py', 'archives/router.py',
    'image_delivery.py', 'thumbnails.py')}
DROP = 'zzzzzzzzzzzzzz-image-cache-20261030.conf'


def inspect():
    return json.loads(run('docker', 'inspect', API))[0]


def topology():
    value = a.topology()
    value['services'].pop(UNITS[1], None)
    domestic = a.inspect('domestic')
    value['containers'][a.DOMAINS['domestic']['container']] = [domestic['Id'], domestic['State']['Running']]
    value['domesticWorker'] = a.worker('domestic')
    value['accountsPid'] = run('systemctl', 'show', a.SERVICE, '-p', 'MainPID', '--value')
    return value


def unit_state(unit):
    pid = int(run('systemctl', 'show', unit, '-p', 'MainPID', '--value'))
    require(pid > 0, 'Overseas service not running')
    proc = Path('/proc') / str(pid)
    require(proc.stat().st_uid == 999, 'Overseas service UID drift')
    files = set()
    for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
        files.update(p for p in run('systemctl', 'show', unit, '-p', key, '--value').split() if p.startswith('/'))
    return dict(pid=pid, cwd=os.readlink(proc / 'cwd'), files={p: digest(p) for p in files})


def verify_package(source):
    data = json.loads((source / 'release.json').read_text())
    require(data['version'] == '0.2.55' and set(data['api']['files']) == FILES, 'Unexpected package scope')
    for name, expected in data['files'].items():
        path = source / name
        require(path.resolve().is_relative_to(source.resolve()) and not path.is_symlink(), 'Unsafe package path')
        require(digest(path) == expected, 'Package checksum mismatch: ' + name)
    return data


def hashes(image):
    previous = a.API_FILES
    try:
        a.API_FILES = FILES
        return a.api_hashes(image)
    finally:
        a.API_FILES = previous


def drop_path(unit):
    return Path('/etc/systemd/system') / (unit + '.d') / DROP


def readiness(url, timeout=40):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            run('curl', '--max-time', str(min(4, remaining)), '-fsS', '-o', '/dev/null', url,
                timeout=min(5, remaining))
            require(time.monotonic() <= deadline, 'Readiness exceeded deadline')
            return
        except (RuntimeError, TimeoutError, __import__('subprocess').TimeoutExpired):
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    raise RuntimeError('Readiness deadline exceeded')
