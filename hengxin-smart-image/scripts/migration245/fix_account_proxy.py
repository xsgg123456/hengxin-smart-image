"""Apply reviewed account transport fixes only on .245; preserve account data."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

BASE = Path('/opt/hengxin-runtime/codex-auth-proxy-20261111')
DAEMON = Path('/opt/hengxin-account-releases/account-management-20261026-ce4baf4/daemon')
HELPER = Path('/opt/hengxin-runtime/codex-upgrade-20261111/upgrade_codex.py')
EXPECTED = {
    'app/account_management/device.py': '21ee8d16bd0e9e67977a6bad6b6430b176754f3b4498439e279e3837b900fbbd',
    'app/execution/workspace.py': '35d4ba0240f5c1ffaaec317c3592ef28899cf04c414f6f640b737ef3465fcb75',
}
SETTINGS = {'HENGXIN_CODEX_PROXY_URL': 'http://127.0.0.1:7890',
            'HENGXIN_ALLOW_LOOPBACK_CODEX_PROXY': '1'}


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Authorized intranet host/root required')
    if hashlib.sha256(HELPER.read_bytes()).hexdigest() != 'd6e34d3911ba8772021ea7254557bb90f7efb62376df2eca84e76f8ecd6e5b01':
        raise RuntimeError('Reviewed maintenance helper changed')
    sys.path.insert(0, str(HELPER.parent))
    import upgrade_codex as m
    manifest = json.loads((BASE / 'candidate-sha256.json').read_text())
    candidates = {}
    for rel, expected in EXPECTED.items():
        path = DAEMON / rel
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Source drift: ' + rel)
        content = (BASE / Path(rel).name).read_bytes()
        if hashlib.sha256(content).hexdigest() != manifest[rel]:
            raise RuntimeError('Candidate drift')
        compile(content, rel, 'exec')
        candidates[path] = content
    envfile = Path('/etc/hengxin-lan/hengxin-codex-accounts.env')
    original_env = envfile.read_text()
    if any(k + '=' in original_env for k in SETTINGS):
        raise RuntimeError('Proxy already configured; inspect drift')
    candidates[envfile] = (original_env.rstrip('\n') + '\n' + ''.join(
        k + '=' + json.dumps(v) + '\n' for k, v in SETTINGS.items())).encode()
    inventory = Path('/opt/hengxin-lan/native-env.json')
    data = json.loads(inventory.read_text())
    if any(k in data[m.ACCOUNT] for k in SETTINGS):
        raise RuntimeError('Inventory already configured')
    data[m.ACCOUNT].update(SETTINGS)
    candidates[inventory] = json.dumps(data, indent=2).encode()
    before = {}
    backup = BASE / 'transaction'
    backup.mkdir(mode=0o700)
    for index, path in enumerate(candidates):
        info = path.stat()
        if path.resolve() != path or info.st_uid != 0 or info.st_nlink != 1:
            raise RuntimeError('Unsafe deployment target')
        before[path] = (path.read_bytes(), info.st_mode & 0o777, info.st_gid)
        m.atomic(backup / str(index), before[path][0], 0o600)
    (backup / 'paths.json').write_text(json.dumps([str(p) for p in before]))
    contexts = {s: m.context(s) for s in m.WORKERS}
    paused, sockets, stopped = [], [], False
    try:
        m.drain(contexts, paused)
        m.gate_account(sockets)
        stopped = True
        m.run(['systemctl', 'stop', m.ACCOUNT], timeout=120)
        if m.prop(m.ACCOUNT, 'MainPID') != '0':
            raise RuntimeError('Account service not stopped')
        for path, (content, _, _) in before.items():
            if path.read_bytes() != content:
                raise RuntimeError('Configuration drift during drain')
        for path, content in candidates.items():
            m.atomic(path, content, before[path][1])
            os.chown(path, 0, before[path][2])
        m.run(['systemctl', 'start', m.ACCOUNT], timeout=120)
        _, env = m.context(m.ACCOUNT)
        if any(env.get(k) != v for k, v in SETTINGS.items()):
            raise RuntimeError('Running account proxy mismatch')
        for path, content in candidates.items():
            if path.read_bytes() != content:
                raise RuntimeError('Installed content mismatch')
        print('APPLIED_ACCOUNT_PROXY', flush=True)
    except Exception:
        if stopped:
            if m.prop(m.ACCOUNT, 'ActiveState') == 'active':
                m.gate_account(sockets)
            m.run(['systemctl', 'stop', m.ACCOUNT], timeout=120)
            for path, (content, mode, group) in before.items():
                m.atomic(path, content, mode)
                os.chown(path, 0, group)
            m.run(['systemctl', 'start', m.ACCOUNT], timeout=120)
            print('ROLLED_BACK_ACCOUNT_PROXY', flush=True)
        raise
    finally:
        errors = []
        for path, inode, mode in sockets:
            try:
                if path.exists() and path.stat().st_ino == inode:
                    path.chmod(mode)
            except OSError:
                errors.append('socket ' + str(path))
        for service in paused:
            try:
                m.control(service, 'resume', contexts)
            except Exception:
                errors.append('consumer ' + service)
        if errors:
            print('RESTORE_UNCONFIRMED', json.dumps(errors), flush=True)
            if sys.exc_info()[0] is None:
                raise RuntimeError('Restoration incomplete')


if __name__ == '__main__':
    main()
