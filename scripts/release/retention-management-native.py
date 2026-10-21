"""Relocate three distinct live native runtimes without changing their execution policy."""
import importlib.util
import json
import os
from pathlib import Path
import re
import time

spec = importlib.util.spec_from_file_location('retirement_native', Path(__file__).with_name('retirement-native.py'))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
m, UNIT, DELETE, RETENTION, UNITS = old.m, old.UNIT, old.DELETE, old.RETENTION, old.UNITS
show, target_argv = old.show, old.target_argv
POLICY = (*old.POLICY, 'SupplementaryGroups', 'NoNewPrivileges', 'ProtectSystem',
          'ProtectHome', 'PrivateTmp', 'SendSIGKILL')
SYSTEMD = Path('/etc/systemd/system')


def snapshot(unit):
    m.run('systemctl', 'is-active', unit, capture=True)
    pid = int(show(unit, 'MainPID'))
    assert pid > 0
    proc = Path('/proc') / str(pid)
    cwd = os.readlink(proc / 'cwd')
    assert cwd == show(unit, 'WorkingDirectory')
    argv = [os.fsdecode(v) for v in (proc / 'cmdline').read_bytes().split(b'\0') if v]
    env = dict(os.fsdecode(v).split('=', 1) for v in (proc / 'environ').read_bytes().split(b'\0') if v)
    policy = {key: show(unit, key) for key in POLICY}
    assert policy['User'] == 'codex' and policy['UMask'] == '0077' and proc.stat().st_uid == 1001
    assert policy['KillMode'] == 'control-group' and policy['Restart'] == 'on-failure'
    if unit == UNIT:
        assert 'app.worker.celery_app:celery_app' in argv
        assert env.get('GENERATION_CONCURRENCY') == '5' and env.get('CODEX_TIMEOUT_SECONDS') == '7200'
    else:
        assert 'app.retention.worker' in argv and '--loop' in argv
        assert ('--deletions-only' in argv) == (unit == DELETE)
        if unit == RETENTION:
            assert env.get('CLI_RETENTION_ENABLED', '').lower() == 'true'
            assert env.get('CLI_RETENTION_BATCH_SIZE') == '25'
    files = {}
    for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
        for path in show(unit, key).split():
            if path.startswith('/'):
                files[path] = m.digest(path)
    assert int(show(unit, 'MainPID')) == pid
    return dict(pid=pid, cwd=cwd, argv=argv, environment=env, policy=policy, files=files)


def snapshots():
    return {unit: snapshot(unit) for unit in UNITS}


def render(row, target):
    target = str(target)
    assert re.fullmatch(r'/opt/hengxin-native-releases/domestic-retention-20261021-[0-9a-f]{7}/backend', target)
    argv = target_argv(row, target)
    assert all(not any(c in arg for c in ('\n', '\r', '"', '\\', '%', '$')) for arg in argv)
    return '[Service]\nWorkingDirectory=' + target + '\nExecStart=\nExecStart=' + ' '.join('"' + a + '"' for a in argv) + '\n'


def prepare(work, source, release, rows):
    # The CLI carries a newer credential patch than the two cleanup services.
    previous = Path(rows[UNIT]['cwd'])
    target = m.prepare_domestic_native(source, release, previous)
    m.private(work / 'native-target', str(target))
    for unit, row in rows.items():
        m.private(work / (unit + '.conf'), render(row, target))
    m.run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'), '-c',
          'from app.retention.state import HISTORY_AGE; assert HISTORY_AGE.total_seconds()==259200; '
          'from app.execution import credential_broker_client; import app.retention.worker', cwd=target)


def stop(unit, timeout=180):
    # SIGTERM is a clean exit with on-failure. Never enqueue systemd's timed SIGKILL stop.
    assert show(unit, 'Restart') == 'on-failure'
    pid = show(unit, 'MainPID')
    if pid == '0':
        return
    m.run('systemctl', 'kill', '--kill-whom=main', '--signal=SIGTERM', unit, timeout=10)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'Native graceful exit timed out; no force stop'
        current = m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True, timeout=min(5, remaining))
        if current == '0':
            return
        assert current == pid, 'Native process restarted while stopping'
        time.sleep(min(.5, remaining))


def switch(work):
    for unit in UNITS:
        assert show(unit, 'MainPID') == '0'
        path = SYSTEMD / (unit + '.service.d') / 'zzzzz-retention-management.conf'
        path.parent.mkdir(exist_ok=True)
        m.private(path, (work / (unit + '.conf')).read_text())
    m.run('systemctl', 'daemon-reload')
    for unit in UNITS:
        assert show(unit, 'WorkingDirectory') == (work / 'native-target').read_text()


def verify(work):
    rows = json.loads((work / 'native-snapshots.private.json').read_text())
    target = (work / 'native-target').read_text()
    transient = {'PWD', 'INVOCATION_ID', 'SYSTEMD_EXEC_PID', 'JOURNAL_STREAM'}
    for unit, before in rows.items():
        after = snapshot(unit)
        assert after['cwd'] == target and after['pid'] != before['pid']
        assert after['policy'] == before['policy'], 'Native execution policy changed'
        clean = lambda env: {k: v for k, v in env.items() if k not in transient}
        assert clean(after['environment']) == clean(before['environment']), 'Native environment changed'
        assert after['argv'] == target_argv(before, target), 'Native command changed'
