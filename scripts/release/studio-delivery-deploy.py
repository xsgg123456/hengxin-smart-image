"""Prepare, switch, verify, resume one native overseas worker; retain admission pause."""
import argparse
import os
from pathlib import Path
import shutil
import time

import studio_delivery_runtime as r


def stage(work, phase, **values):
    r.private(work / 'phase.json', dict(phase=phase, **values))


def prepare(work):
    r.require(not (work / 'prepared.json').exists(), 'Already prepared; inspect evidence')
    r.require(not r.safe(r.TARGET.parent).exists() and not r.safe(r.DROP).exists(), 'Release exists')
    before, saved = r.topology(), r.live()
    old = Path(saved['old'])
    files = r.patch(work)
    r.baseline(old, files)
    source, original_unit = r.tree(old), r.unit()
    # Deliberate sole symlink: reuse installed dependencies; application links are rejected by tree().
    r.require((old / '.venv/bin/python').is_file(), 'Original dependencies absent')
    saved['venv'] = str((old / '.venv').resolve(strict=True))
    r.TARGET.parent.mkdir(mode=0o755)
    shutil.copytree(old, r.TARGET, ignore=shutil.ignore_patterns(*r.IGNORED))
    (r.TARGET / '.venv').symlink_to(saved['venv'], target_is_directory=True)
    for name in files:
        destination = r.safe(r.TARGET / name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / 'src/backend' / name, destination)
        destination.chmod(0o644)
    expected = dict(source)
    expected.update({name: entry['sha256'] for name, entry in files.items()})
    r.require(r.tree(r.TARGET) == expected, 'Unexpected installed files')
    r.require(r.topology() == before and r.live() == {k: saved[k] for k in ('old', 'pid', 'argv')}
              and r.tree(old) == source and r.unit() == original_unit, 'Production changed during preparation')
    r.private(work / 'unit-before.txt', original_unit)
    r.private(work / 'prepared.json', dict(manifest=r.digest(work / 'patch.json'), worker=saved,
              source=source, installed=expected, files=files, unrelated=before))
    r.private(work / 'RECOVERY.md', '''# Controlled recovery
Read phase.json, ATTENTION_REQUIRED.json, prepared.json and unit-before.txt first.
prepare never changes running services. INSTALL_TESTS_PASSED must contain patch.json SHA256
only after isolated tests run against the actual installed directory.
Any failed pause/drain leaves the gate state uncertain: inspect it before taking action.
Any failed stop/start has an unknown outcome: inspect MainPID, actual cwd and argv.
Never blindly rerun switch, kill unknown processes, restart API/outbox/other units, or restore DB.
The database dump is evidence only; automatic restoration is prohibited.
Before worker rollback, keep the gate paused and prove ACTIVE jobs are zero again.
Stop only hengxin-overseas-worker.service after proving its current identity. Remove ONLY
zzzzzzzzz-studio-delivery-20261023.conf after comparing it to this release's saved override;
daemon-reload and start that worker, then verify the saved original cwd/argv and health.
Preserve all other drop-ins and environment configuration. Never restore credentials.
For a failed drain with the original worker still running, prove its original identity,
unit and healthy state before manually restoring the recorded original gate pause value.
After successful switch, leave paused until image recovery and browser acceptance complete.
Write ACCEPTANCE_PASSED with patch.json SHA256 only after both pass; then run resume.
If original gate was paused, resume preserves that pause. Never open it automatically.
''')
    stage(work, 'prepared')
    print('PREPARED; test installed directory and bind INSTALL_TESTS_PASSED to manifest SHA256')


def validate(work):
    state = r.read(work / 'prepared.json')
    r.require(r.digest(work / 'patch.json') == state['manifest'], 'Prepared manifest drift')
    r.require(r.safe(work / 'INSTALL_TESTS_PASSED').read_text().strip() == state['manifest'],
              'Installed tests absent or not bound to manifest')
    r.require(r.patch(work) == state['files'], 'Patch drift')
    r.require(r.tree(Path(state['worker']['old'])) == state['source'], 'Original source drift')
    r.require(r.tree(r.TARGET) == state['installed'], 'Installed source drift')
    r.require((r.TARGET / '.venv').is_symlink() and
              str((r.TARGET / '.venv').resolve(strict=True)) == state['worker']['venv'], 'Dependencies drift')
    r.require(r.topology() == state['unrelated'], 'Unrelated topology changed')
    return state


def switch(work, drain_seconds=600):
    r.require(r.read(work / 'phase.json')['phase'] == 'prepared', 'Inspect prior switch before retry')
    state = validate(work)
    saved = state['worker']
    r.require(r.live() == {k: saved[k] for k in ('old', 'pid', 'argv')}, 'Original worker identity changed')
    r.require(r.unit() == r.safe(work / 'unit-before.txt').read_text(), 'Original unit changed')
    r.require(not r.safe(r.DROP).exists(), 'Existing override refused')
    # Reject later-sorting overrides rather than silently starting on a different directory.
    r.last_override(r.unit())
    original_gate = r.gate()
    r.private(work / 'gate-before.json', original_gate)
    stage(work, 'pause-requested')
    deadline = time.monotonic() + drain_seconds
    paused = r.gate('pause', timeout=min(30, drain_seconds))
    r.require(paused['before'] == original_gate['paused'], 'Gate changed before pause')
    stage(work, 'draining')
    while True:
        left = deadline - time.monotonic()
        r.require(left > 0, 'Drain deadline reached; gate remains paused')
        probe = r.gate(timeout=min(30, left))
        r.require(probe['paused'], 'Gate unexpectedly resumed')
        if probe['active'] == 0:
            break
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    r.require(r.live() == {k: saved[k] for k in ('old', 'pid', 'argv')}, 'Worker identity changed during drain')
    stage(work, 'stop-requested')
    r.run('systemctl', 'stop', r.UNIT, timeout=90)
    r.require(r.run('systemctl', 'show', r.UNIT, '-p', 'MainPID', '--value') == '0', 'Stop unconfirmed')
    stage(work, 'stopped')
    r.backup(work)
    r.require(r.gate()['paused'], 'Gate unexpectedly resumed')
    validate(work)
    r.require(r.unit() == r.safe(work / 'unit-before.txt').read_text(), 'Unit drift before switch')
    r.DROP.parent.mkdir(exist_ok=True)
    with r.safe(r.DROP).open('x') as out:
        out.write(r.dropin(saved))
    r.DROP.chmod(0o644)
    stage(work, 'override-written')
    r.run('systemctl', 'daemon-reload')
    r.private(work / 'unit-installed.txt', r.unit())
    stage(work, 'start-requested')
    r.run('systemctl', 'start', r.UNIT, timeout=60)
    stage(work, 'started')
    verify(work)
    print('WORKER_SWITCHED; gate remains paused pending recovery and browser acceptance')


def verify(work):
    current = r.read(work / 'phase.json')
    r.require(current['phase'] in ('started', 'verified', 'resumed'), 'Worker switch not completed')
    state = validate(work)
    r.require(r.safe(r.DROP).read_text() == r.dropin(state['worker']), 'Override drift')
    r.require(r.unit() == r.safe(work / 'unit-installed.txt').read_text(), 'Installed unit drift')
    deadline = time.monotonic() + 45
    while True:
        try:
            left = deadline - time.monotonic()
            r.require(left > 0, 'Readiness deadline reached')
            live = r.live(timeout=left)
            r.require(live['old'] == str(r.TARGET), 'Wrong worker directory')
            expected = state['worker']['argv'][:]
            expected[:2] = [str(r.TARGET / '.venv/bin/python'), str(r.TARGET / '.venv/bin/celery')]
            r.require(live['argv'] == expected and live['pid'] != state['worker']['pid'], 'Wrong worker command/PID')
            left = deadline - time.monotonic()
            r.require(left > 0, 'Readiness deadline reached')
            r.ready(live, timeout=min(15, left))
            r.require(time.monotonic() <= deadline, 'Readiness deadline reached')
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    r.run('curl', '--max-time', '10', '-fsS', '-o', '/dev/null',
          'http://127.0.0.1:18018/api/overseas/v1/health/ready', timeout=12)
    probe = r.gate()
    desired = r.read(work / 'gate-before.json')['paused'] if current['phase'] == 'resumed' else True
    r.require(probe['paused'] == desired, 'Unexpected gate state')
    r.require(r.topology() == state['unrelated'], 'Unrelated runtime changed')
    stage(work, 'resumed' if current['phase'] == 'resumed' else 'verified', pid=live['pid'],
          version=state['manifest'])
    return state


def resume(work):
    r.require(r.read(work / 'phase.json')['phase'] == 'verified', 'Resume requires verified worker')
    state = verify(work)
    r.require(r.safe(work / 'ACCEPTANCE_PASSED').read_text().strip() == state['manifest'],
              'Image recovery and browser acceptance receipt absent')
    original = r.read(work / 'gate-before.json')['paused']
    stage(work, 'resume-requested')
    result = r.gate('resume', paused=original)
    r.require(result['paused'] == original, 'Gate restore unconfirmed')
    stage(work, 'resumed', version=state['manifest'])
    print('ORIGINAL_GATE_STATE_RESTORED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'switch', 'verify', 'resume'))
    parser.add_argument('--work', type=Path, default=r.WORK)
    parser.add_argument('--drain-seconds', type=int, default=600)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required')
    work = r.safe(args.work)
    r.require(work == r.WORK and work.is_dir() and work.stat().st_uid == 0
              and work.stat().st_mode & 0o077 == 0, 'Expected root-owned private work directory required')
    r.require(1 <= args.drain_seconds <= 3600, 'Invalid drain timeout')
    import fcntl
    lock = r.safe(work / '.deploy.lock').open('a')
    os.chmod(work / '.deploy.lock', 0o600)
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        if args.action == 'switch':
            switch(work, args.drain_seconds)
        else:
            {'prepare': prepare, 'verify': verify, 'resume': resume}[args.action](work)
    except BaseException as exc:
        r.private(work / 'ATTENTION_REQUIRED.json', dict(action=args.action, error=type(exc).__name__,
            message=str(exc) if type(exc) is RuntimeError else 'See private phase evidence',
            recovery='Inspect phase.json and RECOVERY.md. No rollback, DB restore or forced stop performed.'))
        print('ATTENTION_REQUIRED; inspect private phase and recovery evidence')
        raise SystemExit(1) from None
    finally:
        lock.close()


if __name__ == '__main__':
    main()
