"""Install baseline-bound per-domain patches; switch only proven idle native workers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time

import codex_auth_runtime as r


def prepare(work):
    r.require(not (work / 'prepared.json').exists(), 'Existing preparation requires inspection')
    r.require(not (r.SYSTEMD / r.BROKER).exists(), 'Existing broker unit requires inspection')
    before, domains = r.topology(), {}
    for domain, config in r.DOMAINS.items():
        old, _, pid = r.live(domain)
        target = Path(config['target'])
        r.require(not target.parent.exists() and not r.drop_path(domain).exists(), 'Release target already exists')
        files = r.patch(work, domain)
        r.baseline(old, files)
        info = r.worker_probe(domain, 'verify', work)
        domains[domain] = dict(old=str(old), pid=pid, files=files, source=r.tree(old), node=info['node'])
        r.private(work / (domain + '-unit-before.txt'), r.run('systemctl', 'cat', config['unit']))
    # No mutations to existing services, account credentials or business directories.
    for domain, state in domains.items():
        target, old = Path(r.DOMAINS[domain]['target']), Path(state['old'])
        target.parent.mkdir(mode=0o755)
        shutil.copytree(old, target, symlinks=True,
                        ignore=shutil.ignore_patterns('.venv', '__pycache__', '.pytest_cache'))
        (target / '.venv').symlink_to(old / '.venv', target_is_directory=True)
        for name in state['files']:
            destination = target / name
            r.require(not destination.is_symlink(), 'Linked patch destination refused')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(work / 'src' / domain / name, destination)
            destination.chmod(0o644)
        state['installed'] = r.tree(target)
        expected = dict(state['source'])
        expected.update({name: entry['sha256'] for name, entry in state['files'].items()})
        r.require(state['installed'] == expected, 'Unexpected change outside patch manifest')
    state = dict(manifest=r.digest(work / 'patch.json'), domains=domains, unrelated=before)
    r.require(r.topology() == before, 'Production topology changed during preparation')
    r.private(work / 'prepared.json', state)
    r.private(work / 'RECOVERY.md', 'Inspect *-stage.json and FAILURE.json before any action.\n'
        'Preparation never changes running services. Broker failure leaves workers unchanged.\n'
        'A drained/stopped domain may be restarted on its original configuration ONLY after checking '
        'actual PID/cwd/queues and confirming no active execution. If an override was written, '
        'inspect its exact content and the saved *-unit-before.txt before removing only this release override.\n'
        'After a new worker started, it can have accepted queued work: drain it again before any rollback.\n'
        'Never restore credentials or databases. Never stop another worker, outbox or container.\n')
    print('PREPARED; run installed-directory tests and bind INSTALL_TESTS_PASSED to patch.json SHA256')


def validate(work):
    state = json.loads((work / 'prepared.json').read_text())
    r.require(r.digest(work / 'patch.json') == state['manifest'], 'Prepared manifest drift')
    r.require((work / 'INSTALL_TESTS_PASSED').read_text().strip() == state['manifest'],
              'Installed tests are absent or not bound to this manifest')
    r.require(r.topology() == state['unrelated'], 'Unrelated production topology changed')
    for domain, saved in state['domains'].items():
        r.require(r.patch(work, domain) == saved['files'], 'Patch changed since preparation')
        r.require(r.tree(Path(saved['old'])) == saved['source'], 'Original source tree drift')
        r.require(r.tree(Path(r.DOMAINS[domain]['target'])) == saved['installed'], 'Installed source drift')
        stage = work / (domain + '-stage.json')
        current = json.loads(stage.read_text()) if stage.exists() else {}
        expected_path, expected_pid = saved['old'], saved['pid']
        if current.get('phase') in ('started', 'verified'):
            expected_path, expected_pid = r.DOMAINS[domain]['target'], current['pid']
            r.require(r.drop_path(domain).read_text() == r.dropin(domain, saved['node']), 'Installed override drift')
        cwd, _, pid = r.live(domain)
        r.require(str(cwd) == expected_path and pid == expected_pid, 'Worker identity changed since recorded stage')
    return state


def start_broker(work):
    validate(work)
    r.require(not (work / 'broker-stage.json').exists(), 'Inspect prior broker attempt before retry')
    path = r.SYSTEMD / r.BROKER
    r.require(not path.exists(), 'Existing broker unit refused')
    r.private(work / 'broker-stage.json', {'phase': 'creating'})
    # Create a dedicated socket-access group, without granting access to business data.
    import grp
    try:
        grp.getgrnam(r.GROUP)
    except KeyError:
        r.run('groupadd', '--system', r.GROUP)
    path.write_text(r.broker_unit())
    path.chmod(0o644)
    r.run('systemctl', 'daemon-reload')
    r.run('systemctl', 'enable', '--now', r.BROKER)
    r.private(work / 'broker-stage.json', {'phase': 'started'})
    deadline = time.monotonic() + 15
    while not Path(r.SOCKET).is_socket() and time.monotonic() < deadline:
        time.sleep(0.25)
    for domain in r.DOMAINS:
        r.probe_access(domain)
    r.private(work / 'broker-stage.json', {'phase': 'ready-both-uids'})
    print('BROKER_READY_BOTH_UIDS')


def switch(work, domain):
    state = validate(work)
    r.require(json.loads((work / 'broker-stage.json').read_text())['phase'] == 'ready-both-uids',
              'Credential broker readiness absent')
    r.require(not (work / (domain + '-stage.json')).exists(), 'Inspect prior domain attempt before retry')
    config, saved = r.DOMAINS[domain], state['domains'][domain]
    old, _, pid = r.live(domain)
    r.require(str(old) == saved['old'] and pid == saved['pid'], 'Live worker changed since preparation')
    r.require(not r.drop_path(domain).exists(), 'Existing release override refused')
    r.require(r.run('systemctl', 'cat', config['unit']) == (work / (domain + '-unit-before.txt')).read_text(),
              'Worker unit changed since preparation')
    r.probe_access(domain)
    r.private(work / (domain + '-stage.json'), {'phase': 'draining'})
    result = r.worker_probe(domain, 'drain-stop', work)
    r.require(result['node'] == saved['node'], 'Worker node changed during drain')
    r.require(json.loads((work / (domain + '-stage.json')).read_text())['phase'] == 'stopped',
              'No stopped proof; refuse switch')
    path = r.drop_path(domain)
    path.parent.mkdir(exist_ok=True)
    with path.open('x') as out:
        out.write(r.dropin(domain, saved['node']))
    path.chmod(0o644)
    r.private(work / (domain + '-stage.json'), {'phase': 'override-written'})
    r.run('systemctl', 'daemon-reload')
    r.private(work / (domain + '-stage.json'), {'phase': 'start-requested'})
    r.run('systemctl', 'start', config['unit'])
    r.private(work / (domain + '-stage.json'), {'phase': 'started', 'pid': r.live(domain)[2]})
    verify_domain(work, domain)
    r.require(r.topology() == state['unrelated'], 'Unrelated topology changed after switch')
    r.private(work / (domain + '-stage.json'), {'phase': 'verified', 'pid': r.live(domain)[2]})
    print('SWITCHED_AND_VERIFIED', domain)


def verify_domain(work, domain):
    config = r.DOMAINS[domain]
    deadline = time.monotonic() + 40
    while True:
        try:
            cwd, env, pid = r.live(domain)
            r.require(str(cwd) == config['target'], 'Worker not running installed release')
            r.require(env.get(config['prefix'] + 'CODEX_AUTH_BROKER_SOCKET') == r.SOCKET, 'Broker environment missing')
            group = r.run('getent', 'group', r.GROUP).split(':')[2]
            groups = next(line.split()[1:] for line in Path(f'/proc/{pid}/status').read_text().splitlines()
                          if line.startswith('Groups:'))
            r.require(group in groups, 'Actual worker lacks broker supplementary group')
            r.worker_probe(domain, 'verify', work, timeout=max(1, deadline - time.monotonic()))
            r.require(time.monotonic() <= deadline, 'Worker readiness deadline exceeded')
            return
        except (RuntimeError, ValueError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def verify(work):
    state = validate(work)
    for domain in r.DOMAINS:
        verify_domain(work, domain)
        r.probe_access(domain)
        r.private(work / (domain + '-stage.json'), {'phase': 'verified', 'pid': r.live(domain)[2]})
    for address in ('http://127.0.0.1:18008/api/v1/health/ready',
                    'http://127.0.0.1:18018/api/overseas/v1/health/ready'):
        r.run('curl', '--max-time', '10', '-fsS', '-o', '/dev/null', address, timeout=12)
    r.require(r.topology() == state['unrelated'], 'Unrelated topology changed')
    r.private(work / 'VERIFIED', state['manifest'])
    print('BOTH_WORKERS_POOL_5_HEALTHY; real image acceptance still required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'start-broker', 'switch-domestic', 'switch-overseas', 'verify'))
    parser.add_argument('--work', type=Path, default=r.WORK)
    args = parser.parse_args()
    r.require(os.geteuid() == 0, 'Root required for controlled host deployment')
    import fcntl
    lock = (args.work / '.deploy.lock').open('a')
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        if args.action.startswith('switch-'):
            switch(args.work, args.action.removeprefix('switch-'))
        else:
            {'prepare': prepare, 'start-broker': start_broker, 'verify': verify}[args.action](args.work)
    except BaseException as exc:
        r.private(args.work / 'FAILURE.json', {'action': args.action, 'type': type(exc).__name__,
            'recovery': 'Read stage evidence and RECOVERY.md; no automatic rollback or forced stop performed'})
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    main()
