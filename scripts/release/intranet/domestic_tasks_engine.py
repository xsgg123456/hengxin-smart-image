"""Scoped migration, reboot-safe stop fencing and forward-only recovery."""
from contextlib import contextmanager
import json
from pathlib import Path

import engine
import domestic_tasks_history as history
import joint_studio_credentials as processes
import joint_studio_fence as fence
import joint_studio_forward as forward
import operations
import scopes
import snapshot


def restart_policies(u):
    services = json.loads(u.COMPOSE.read_bytes())['services']
    result = {}
    for name in u.APPS:
        policy, separator, retries = services[name].get('restart', 'no').partition(':')
        if policy not in ('no', 'always', 'unless-stopped', 'on-failure') or (
                separator and (policy != 'on-failure' or not retries.isdigit())):
            raise RuntimeError('Unsupported domestic restart policy')
        result[name] = {'Name': policy, 'MaximumRetryCount': int(retries) if separator else 0}
    return result


def check_restarts(u):
    """Inspect runtime policy, including retry count, before accepting a start."""
    expected, live = restart_policies(u), u.containers()
    if set(live) != set(expected) or any(
            live[name]['HostConfig']['RestartPolicy'] != policy for name, policy in expected.items()):
        raise RuntimeError('Domestic restart policy differs from compose')


def freeze(u):
    """Disable only domestic container restarts before any schema mutation."""
    path = u.WORK / 'tasks-restarts.json'
    live = u.containers()
    if not path.exists():
        policies = restart_policies(u)
        if set(live) != set(policies):
            raise RuntimeError('Domestic restart inventory differs')
        expected = {}
        for name, info in live.items():
            policy = info['HostConfig']['RestartPolicy']
            if policy != policies[name]:
                raise RuntimeError('Unexpected domestic restart policy')
            expected[name] = {'id': info['Id'], 'policy': policy}
        u.write(path, json.dumps(expected, sort_keys=True).encode(), exclusive=True)
    else:
        u.safe(path)
        expected = json.loads(path.read_bytes())
        if set(expected) != set(u.APPS):
            raise RuntimeError('Domestic restart inventory differs')
    for name in u.APPS:
        u.run(['docker', 'update', '--restart=no', 'hengxin-lan-' + name])


def stopped(u):
    for name in u.NATIVE:
        processes.stopped(u, name)
    if any(row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name'] != 'no'
           for row in u.containers().values()):
        raise RuntimeError('Domestic containers are not durably stopped')


def backup(u, descriptor):
    report = u.WORK / 'data-backup/verified.json'
    if not report.exists():
        operations.backup(u, u.WORK, scope='domestic', pass_fds=(descriptor,))
    u.safe(report)
    value = json.loads(report.read_bytes())
    path = report.parent / 'domestic.dump'
    u.safe(path)
    if (set(value) != {'domestic'} or path.stat().st_size <= 0
            or value['domestic'] != {'bytes': path.stat().st_size, 'sha256': operations.file_sha(path)}):
        raise RuntimeError('Domestic migration backup evidence differs')
    return u.digest(report.read_bytes())


def migrate(u, ctx, before, descriptor):
    fence.assert_held(u, descriptor)
    stopped(u)
    if snapshot.schemas(u) != before['schema'] or u.data_identity() != before['data']:
        raise RuntimeError('Schema/data changed before Tasks migration')
    backup_sha = backup(u, descriptor)
    row = {'schema': before['schema'], 'data': before['data'], 'target': '0044',
           'backup_sha256': backup_sha, 'history': history.capture(u), 'phase': 'migrating'}
    engine._save('tasks-migration.json', row, exclusive=True)
    worker = dict(ctx['hengxin-vps-codex-worker'])
    worker['env'] = dict(worker['env'], DOMESTIC_STUDIO_MIGRATION_FENCE='1')
    u.native_run(worker, module='alembic', args=('upgrade', '0044'),
                 cwd=str(u.RELEASE / 'backend'), timeout=300, pass_fds=(descriptor,))
    check_migration(u, before, descriptor)


def check_migration(u, before, descriptor):
    row = engine._read('tasks-migration.json')
    if (row.get('target') != '0044' or row.get('schema') != before['schema']
            or row.get('data') != before['data'] or row.get('phase') not in ('migrating', 'migrated')
            or row.get('backup_sha256') != backup(u, descriptor)
            or snapshot.schemas(u) != dict(before['schema'], domestic='0044')
            or u.data_identity() != before['data']):
        raise RuntimeError('Tasks migration evidence/schema/data differs')
    if row['phase'] == 'migrating':
        stopped(u)
        history.verify(u, row['history'])
        row['phase'] = 'migrated'
        engine._save('tasks-migration.json', row)


@contextmanager
def context(item, descriptor):
    """Must be nested inside the ordinary domestic scope context and host lock."""
    u, before = engine.u, item['before']
    original_stop, original_start, original_app = u.stop_apps, u.start_apps, u.app_command
    original_recover, original_apply = engine.recover, engine.apply
    override = u.STOP_OVERRIDE + b'[Unit]\nConditionPathExists=/dev/null/hengxin-tasks-never\n'

    def app(action, names, candidate=False):
        if action == 'up' and names and not candidate:
            if not set(names) <= set(u.APPS):
                raise RuntimeError('Non-application compose action refused')
            # Explicit recreation restores the compose restart policy and
            # prevents reviving a stopped container with old source mounts.
            return u.compose('up', '-d', '--no-deps', '--pull', 'never', '--force-recreate', *names)
        return original_app(action, names, candidate=candidate)

    def verify_restarts():
        check_restarts(u)

    def start(ctx):
        original_start(ctx)
        verify_restarts()

    def apply():
        result = original_apply()
        verify_restarts()  # Also covers tasks-finish / an existing applied receipt.
        return result

    def stop_and_migrate():
        freeze(u)
        original_stop()
        state = engine._load_state(engine._read('prepared.json'))
        migrate(u, state['ctx'], before, descriptor)

    def guarded_recover():
        fence.assert_held(u, descriptor)
        if (u.WORK / 'tasks-migration.json').exists():
            state = engine._load_state(engine._read('prepared.json'))
            fence.wait_database(u, state['ctx']['hengxin-vps-codex-worker'])
        if snapshot.schemas(u) != before['schema']:
            u.app_command('stop', u.ENTRIES)
            raise RuntimeError('Tasks migration committed or drifted; use tasks-recover for forward recovery')
        with scopes.replace(u, stop_apps=original_stop):
            result = original_recover()
            verify_restarts()
            return result

    with scopes.replace(u, stop_apps=stop_and_migrate, start_apps=start, app_command=app, STOP_OVERRIDE=override), \
         scopes.replace(engine, recover=guarded_recover, apply=apply):
        yield


def resume(item, descriptor):
    u = engine.u
    baseline = engine._read('prepared.json')
    state = engine._load_state(baseline)
    engine._check(baseline, recovering=True, state=state)
    check_migration(u, item['before'], descriptor)
    if u.validate_release() != baseline['release_manifest']:
        raise RuntimeError('Tasks candidate changed during recovery')
    if (u.WORK / 'applied.json').exists():
        return engine.apply()
    u.app_command('stop', u.ENTRIES)
    engine._quiesce(state)
    engine._phase(state, 'recovering')
    freeze(u)
    forward.stop_existing(u)
    stopped(u)
    engine._check(baseline, recovering=True, state=state)
    engine._phase(state, 'switching')
    for name in u.NATIVE:
        u.write(engine._dropin(name), (u.WORK / (name + '.conf')).read_bytes(), mode=0o644)
    u.write(u.COMPOSE, (u.WORK / 'compose.candidate.json').read_bytes())
    engine._phase(state, 'starting')
    try:
        u.start_apps(state['ctx'])
        engine._check(baseline, recovering=True, state=state)
        check_migration(u, item['before'], descriptor)
        if u.validate_release() != baseline['release_manifest']:
            raise RuntimeError('Tasks candidate drift after forward start')
        engine._save('applied.json', {'manifest': baseline['release_manifest']}, exclusive=True)
    except BaseException:
        u.app_command('stop', u.ENTRIES)
        raise
