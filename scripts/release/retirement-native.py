"""Snapshot actual native processes; preserve policy while replacing only code paths."""
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
UNIT = 'hengxin-vps-codex-worker'
DELETE = 'hengxin-domestic-deletions'
RETENTION = 'hengxin-retention'
UNITS = (UNIT, DELETE, RETENTION)
POLICY = ('User', 'Group', 'UMask', 'KillMode', 'MemoryMax', 'MemoryHigh', 'TasksMax',
          'CPUQuotaPerSecUSec', 'TimeoutStopUSec', 'Restart', 'EnvironmentFiles', 'Environment')


def show(unit, key):
    return m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True)


def snapshot(unit):
    m.run('systemctl', 'is-active', unit, capture=True)
    pid = int(show(unit, 'MainPID'))
    assert pid > 0, 'Native PID unavailable'
    proc = Path('/proc') / str(pid)
    cwd = os.readlink(proc / 'cwd')
    assert cwd == show(unit, 'WorkingDirectory'), 'Running/configured native cwd differs'
    argv = [os.fsdecode(v) for v in (proc / 'cmdline').read_bytes().split(b'\0') if v]
    env = dict(os.fsdecode(v).split('=', 1) for v in (proc / 'environ').read_bytes().split(b'\0') if v)
    policy = {key: show(unit, key) for key in POLICY}
    assert policy['User'] == 'codex' and policy['UMask'] == '0077'
    assert policy['KillMode'] == 'control-group' and proc.stat().st_uid == 1001
    assert env.get('CLI_RETENTION_ENABLED', 'false').lower() == ('true' if unit == RETENTION else 'false')
    if unit == UNIT:
        assert 'app.worker.celery_app:celery_app' in argv
        assert env.get('GENERATION_CONCURRENCY') == '5' and env.get('CODEX_TIMEOUT_SECONDS') == '7200'
    else:
        assert 'app.retention.worker' in argv and '--loop' in argv
        assert ('--deletions-only' in argv) == (unit == DELETE)
        if unit == RETENTION:
            assert env.get('CLI_RETENTION_BATCH_SIZE') == '25'
    files = {}
    for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
        for path in show(unit, key).split():
            if path.startswith('/'):
                files[path] = m.digest(path)
    # ExecStart carries timestamps/PID metadata after daemon-reload: inspect actual argv instead.
    assert int(show(unit, 'MainPID')) == pid, 'Native process changed during inspection'
    return dict(pid=pid, cwd=cwd, argv=argv, environment=env, policy=policy, files=files)


def all_snapshots():
    return {unit: snapshot(unit) for unit in UNITS}


def render(old, target):
    target = str(target)
    assert target.startswith('/opt/hengxin-native-releases/domestic-retire-')
    assert all(c not in target for c in ('\n', ' ', '"', '%'))
    argv = target_argv(old, target)
    assert argv[0].startswith(target + '/.venv/bin/'), 'Unexpected native executable'
    assert all(not any(c in arg for c in ('\n', '"', '\\', '%')) for arg in argv)
    return '[Service]\nWorkingDirectory=' + target + '\nExecStart=\nExecStart=' + ' '.join('"' + arg + '"' for arg in argv) + '\n'


def target_argv(old, target):
    assert PurePosixPath(old['argv'][0]).name in ('python', 'python3', 'python3.12'), 'Unexpected native interpreter'
    # A shared old venv may resolve its shebang to a different release than the code cwd.
    # Always select the prepared target interpreter, especially when uv.lock has changed.
    return [str(PurePosixPath(target) / '.venv/bin/python'), *[
        str(target) + arg[len(old['cwd']):] if arg.startswith(old['cwd'] + '/') else arg
        for arg in old['argv'][1:]]]


def prepare(work, source, release, snapshots):
    old = Path(snapshots[UNIT]['cwd'])
    assert all(row['cwd'] == str(old) for row in snapshots.values()), 'Native code pointers differ'
    same = all((source / 'backend' / name).read_bytes() == (old / name).read_bytes()
               for name in ('pyproject.toml', 'uv.lock'))
    target = m.prepare_domestic_native(source, release, old) if same else m.r.prepare_native(source, release)
    m.private(work / 'native-target', str(target))
    for unit, row in snapshots.items():
        m.private(work / (unit + '.conf'), render(row, target))
    m.run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'), '-m',
          'app.retention.worker', '--help', cwd=target, capture=True)


def switch(work):
    for unit in UNITS:
        assert show(unit, 'MainPID') == '0', 'Old native process still running'
        path = Path('/etc/systemd/system') / (unit + '.service.d') / 'zz-retirement.conf'
        path.parent.mkdir(exist_ok=True)
        m.private(path, (work / (unit + '.conf')).read_text())
    m.run('systemctl', 'daemon-reload')
    target = (work / 'native-target').read_text()
    for unit in UNITS:
        assert show(unit, 'WorkingDirectory') == target, 'Native override did not win'


def verify(work):
    before = json.loads((work / 'native-snapshots.private.json').read_text())
    target = (work / 'native-target').read_text()
    for unit, old in before.items():
        new = snapshot(unit)
        assert new['cwd'] == target and new['pid'] != old['pid']
        assert new['policy'] == old['policy'], 'Native policy changed'
        # PWD is a service-manager/process detail; all business environment values stay exact.
        clean = lambda env: {k: v for k, v in env.items()
                             if k not in ('PWD', 'INVOCATION_ID', 'SYSTEMD_EXEC_PID', 'JOURNAL_STREAM')}
        assert clean(new['environment']) == clean(old['environment']), 'Native environment changed'
        assert new['argv'] == target_argv(old, target), 'Native command changed'
