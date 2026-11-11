"""Hash-guarded .245-only loopback proxy deployment adaptation; never start services."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat

PRIVATE = Path('/var/lib/hengxin-migration/lan-245')
SOURCE = PRIVATE / 'source-runtime.json'
CANDIDATE = PRIVATE / 'sandbox-proxy-applied'
PLAN = PRIVATE / 'sandbox-proxy-plan.json'
TARGETS = (
    Path('/opt/hengxin-native-releases/domestic-record-filters-20261022-2f08f8f/backend/app/execution/workspace.py'),
    Path('/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend/app/execution/workspace.py'),
)
ENV_FILES = tuple(Path('/etc/hengxin-lan') / (name + '.env') for name in
                  ('hengxin-vps-codex-worker', 'hengxin-overseas-worker'))
FLAG = 'HENGXIN_ALLOW_LOOPBACK_CODEX_PROXY'
PROXY = 'HENGXIN_CODEX_PROXY_URL'
OLD_GATE = "if (os.environ.get('APP_ENV') not in ('test', 'development')"
NEW_GATE = "if ((os.environ.get('APP_ENV') not in ('test', 'development')\n                and os.environ.get('HENGXIN_ALLOW_LOOPBACK_CODEX_PROXY') != '1')"
OLD_CONTROL = 'or any(c.isspace() for c in proxy)):'
NEW_CONTROL = 'or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in proxy)):'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def safe(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError('unsafe target path')
    if path.exists() and path.is_file() and path.stat().st_nlink != 1:
        raise ValueError('hard links refused')
    return path


def patched_source(content, expected):
    if digest(content) != expected:
        raise ValueError('workspace source hash drift')
    text = content.decode()
    if text.count(OLD_GATE) != 1 or text.count(OLD_CONTROL) != 1:
        raise ValueError('proxy validation anchor drift')
    if "'--unshare-net'" in text or "'--unshare-all'" in text:
        raise ValueError('unexpected isolated network namespace')
    text = text.replace(OLD_GATE, NEW_GATE).replace(OLD_CONTROL, NEW_CONTROL)
    compile(text, 'workspace.py', 'exec')
    return text.encode()


def patched_env(content):
    text = content.decode()
    if '\0' in text or re.search(r'(?m)^\s*(?:' + FLAG + '|' + PROXY + r')\s*=', text):
        raise ValueError('proxy environment already configured or invalid')
    return (text + ('' if text.endswith('\n') else '\n') + FLAG + '="1"\n'
            + PROXY + '="http://127.0.0.1:7890"\n').encode()


def collect(data):
    changes = []
    for path in TARGETS:
        safe(path)
        original = path.read_bytes()
        expected = data['native_hashes'][str(path)]['sha256']
        changes.append((path, original, patched_source(original, expected)))
    return changes


def exclusive(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(data):
    safe(PRIVATE)
    safe(CANDIDATE)
    safe(PLAN)
    if CANDIDATE.exists():
        raise FileExistsError('deployment candidate already exists')
    changes = collect(data)
    for path in ENV_FILES:
        safe(path)
    manifest = {'source_changes': [{'path': str(p), 'source_sha256': digest(a), 'target_sha256': digest(b)}
                                   for p, a, b in changes],
                'environment_files': [str(p) for p in ENV_FILES],
                'environment_keys': [FLAG, PROXY], 'proxy': 'http://127.0.0.1:7890',
                'default_production_policy': 'proxy remains denied without explicit flag=1',
                'changes': 'explicit loopback opt-in; reject all C0/DEL control characters; preserve sandbox policy'}
    if not all(p.exists() for p in ENV_FILES):
        exclusive(PLAN, json.dumps(manifest, indent=2).encode())
        return 'plan-only: native worker environment files are not ready; nothing patched'
    for path in ENV_FILES:
        st = path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
            raise ValueError('private worker environment required')
        original = path.read_bytes()
        changes.append((path, original, patched_env(original)))
    snapshots = [p.stat() for p, _, _ in changes]
    if any(st.st_dev != PRIVATE.stat().st_dev for st in snapshots):
        raise ValueError('atomic deployment requires same filesystem')
    CANDIDATE.mkdir(mode=0o700)
    manifest['targets'] = [{'path': str(p), 'source_sha256': digest(a), 'target_sha256': digest(b)} for p, a, b in changes]
    exclusive(CANDIDATE / 'manifest.json', json.dumps(manifest, indent=2).encode())
    for i, (_, original, patched) in enumerate(changes):
        exclusive(CANDIDATE / (str(i) + '.source'), original)
        exclusive(CANDIDATE / (str(i) + '.patched'), patched)
        exclusive(CANDIDATE / (str(i) + '.install'), patched)
    for (path, original, _), st in zip(changes, snapshots):
        safe(path)
        if path.stat().st_ino != st.st_ino or path.read_bytes() != original:
            raise ValueError('target changed after preflight; backups retained')
    for i, ((path, original, patched), st) in enumerate(zip(changes, snapshots)):
        safe(path)
        if path.stat().st_ino != st.st_ino or path.read_bytes() != original:
            raise ValueError('target changed during deployment; inspect private journal')
        temporary = CANDIDATE / (str(i) + '.install')
        os.chmod(temporary, stat.S_IMODE(st.st_mode))
        if hasattr(os, 'chown'):
            os.chown(temporary, st.st_uid, st.st_gid)
        os.replace(temporary, path)
        if digest(path.read_bytes()) != digest(patched):
            raise RuntimeError('patch verification failed')
        exclusive(CANDIDATE / (str(i) + '.applied'), digest(patched).encode())
    return 'applied: two workspace files and two private worker environments; no services restarted'


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('target host/root required')
    safe(SOURCE)
    safe(PRIVATE)
    if PRIVATE.stat().st_uid != 0 or PRIVATE.stat().st_mode & 0o077:
        raise ValueError('private deployment directory required')
    for path in (*TARGETS, *ENV_FILES):
        safe(path)
        if path.exists() and path.stat().st_uid != 0:
            raise ValueError('root-owned deployment targets required')
    print(prepare(json.loads(SOURCE.read_text())))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Sandbox proxy deployment refused; inspect target identity, hashes and private candidates.')
