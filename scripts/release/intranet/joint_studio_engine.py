"""Extend the existing release journal with a forward-only domestic migration."""
from contextlib import ExitStack, contextmanager
import json
import hashlib
from pathlib import Path

import engine
import joint_studio_config as config
import joint_studio_paths as paths
import joint_studio_fence as fence
import joint_studio_ingress as ingress
import operations
import scope_snapshot
import scopes
import snapshot


def verify_backup(u, report):
    u.safe(report)
    content = json.loads(report.read_bytes())
    if set(content) != {'domestic', 'overseas', 'accounts_config'}:
        raise RuntimeError('Incomplete migration backup receipt')
    for side in ('domestic', 'overseas', 'accounts_config'):
        path = report.parent / (side + '.dump' if side != 'accounts_config' else 'accounts-config.tar')
        u.safe(path)
        expected = content[side]
        if side != 'accounts_config' and path.stat().st_size != expected['bytes']:
            raise RuntimeError('Migration backup size changed')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != (expected['sha256'] if side != 'accounts_config' else expected):
            raise RuntimeError('Migration backup checksum changed')


def migrate(u, contexts, expected_data, expected_schema):
    with fence.hold(u) as descriptor:
        before = snapshot.schemas(u)
        if before != expected_schema or before.get('domestic') != '0032' or u.data_identity() != expected_data:
            raise RuntimeError('Domestic schema or data identity changed before migration')
        operations.backup(u, u.WORK, pass_fds=(descriptor,))
        report = u.WORK / 'data-backup/verified.json'
        verify_backup(u, report)
        marker = {'before': before, 'data': expected_data, 'backup_sha256': u.digest(report.read_bytes()),
                  'target': '0043', 'phase': 'migrating'}
        u.write(u.WORK / 'domestic-migration.json', json.dumps(marker, sort_keys=True).encode(), exclusive=True)
        ctx = dict(contexts['hengxin-vps-codex-worker'])
        ctx['env'] = dict(ctx['env'], **config.wiring.native_environment(), DOMESTIC_STUDIO_MIGRATION_FENCE='1')
        u.native_run(ctx, module='alembic', cwd=str(u.RELEASE / 'backend'), args=('upgrade', '0043'),
                     timeout=300, pass_fds=(descriptor,))
        after = snapshot.schemas(u)
        if after != dict(before, domestic='0043') or u.data_identity() != expected_data:
            raise RuntimeError('Unexpected schema or data identity after migration')
        marker.update(phase='migrated', after=after)
        u.write(u.WORK / 'domestic-migration.json', json.dumps(marker, sort_keys=True).encode())


def check_migration(u, baseline, expected_overseas):
    schemas = snapshot.schemas(u)
    if schemas != {'domestic': '0043', 'overseas': expected_overseas}:
        raise RuntimeError('Forward recovery requires the verified upgraded schema')
    if u.data_identity() != baseline['data_containers']:
        raise RuntimeError('Data container identity changed')
    marker, report = u.WORK / 'domestic-migration.json', u.WORK / 'data-backup/verified.json'
    u.safe(marker)
    verify_backup(u, report)
    value = json.loads(marker.read_bytes())
    if (value.get('target') != '0043' or value.get('data') != baseline['data_containers']
            or value.get('before') != {'domestic': '0032', 'overseas': expected_overseas}
            or value.get('backup_sha256') != u.digest(report.read_bytes())
            or value.get('phase') not in ('migrating', 'migrated')):
        raise RuntimeError('Migration evidence differs')


def recover_or_refuse(u, expected_schema, recover, quiesce=None):
    if snapshot.schemas(u) == expected_schema:
        return recover()
    # Never let the original recovery put old code on a changed schema.
    u.app_command('stop', u.ENTRIES)
    if quiesce:
        quiesce()
    raise RuntimeError('Domestic migration committed or schema drifted; forward recovery is required')


@contextmanager
def context(backend, frontends, expected_schema, external_fence=None, private_gateway=True):
    """Caller holds the existing single release lock through every phase."""
    u = engine.u
    backend = Path(backend)
    frontend_paths = {name: Path(value) for name, value in frontends.items()}
    original = {name: getattr(u, name) for name in ('contexts', 'validate_release', 'probe_candidate',
                                                      'stop_apps', 'start_apps', 'candidate_compose',
                                                      'app_command', 'health')}
    recover = engine.recover
    original_prepare, original_check = engine.prepare, engine._check
    original_restore = engine._restore_sockets
    original_quiesce = engine._quiesce
    gateway = (ingress.PrivateIngress(u, original['app_command'], original['health'], original_restore,
                                      original['start_apps'], original_quiesce)
               if private_gateway else None)
    runtime_context = {}
    if expected_schema.get('domestic') != '0032' or not expected_schema.get('overseas'):
        raise RuntimeError('Joint upgrade requires the verified domestic 0032 schema')
    binding = {'backend': str(backend), 'frontends': {k: str(v) for k, v in frontend_paths.items()},
               'schema': dict(expected_schema)}

    def contexts():
        result = original['contexts']()
        runtime_context.clear()
        runtime_context.update(result)
        paths.identities(result)
        return result

    def validate_release():
        hashes = {}
        for root in sorted({backend, *frontend_paths.values()}):
            with scopes.replace(u, RELEASE=root):
                hashes[str(root)] = original['validate_release']()
        return u.digest(json.dumps({'binding': binding, 'manifests': hashes}, sort_keys=True).encode())

    def probe_candidate(ctx, candidate):
        original['probe_candidate'](ctx, candidate)
        u.compose('run', '--rm', '--no-deps', '--pull', 'never', '--entrypoint', 'python',
                  scopes.DOMESTIC_PUBLISHER, '-B', '-c',
                  'import app.modules.domestic_studio.skill_publisher', config=candidate)
        u.native_run(ctx['hengxin-vps-codex-worker'], module='alembic', args=('--version',), timeout=30)

    def prepare():
        result = original_prepare()
        baseline = engine._read('prepared.json')
        for name in u.NATIVE:
            data = config.native_dropin(name, backend)
            u.write(u.WORK / (name + '.conf'), data)
            baseline['dropins'][name] = u.digest(data)
        baseline['joint_binding'] = binding
        engine._save('prepared.json', baseline)
        return result

    def check(baseline, recovering=False, state=None):
        if baseline.get('joint_binding') != binding:
            raise RuntimeError('Joint transaction binding differs')
        return original_check(baseline, recovering=recovering, state=state)

    def stop_and_migrate():
        original['stop_apps']()
        migrate(u, runtime_context, engine._read('prepared.json')['data_containers'], expected_schema)

    def start(ctx):
        with scopes.replace(u, APPS=tuple(dict.fromkeys((*u.APPS, scopes.DOMESTIC_PUBLISHER)))):
            if gateway:
                gateway.start(original['start_apps'], ctx)
            else:
                original['start_apps'](ctx)

    def guarded_recover():
        def restore_original():
            # Recovery before migration must never call the migration hook or
            # try to start the not-yet-existing publisher service.
            with scopes.replace(u, stop_apps=original['stop_apps'], start_apps=original['start_apps'],
                                app_command=original['app_command'], health=original['health']), \
                 scopes.replace(engine, _restore_sockets=original_restore, _quiesce=original_quiesce):
                return recover()
        def checked_recover():
            if (u.WORK / 'domestic-migration.json').exists():
                baseline = engine._read('prepared.json')
                state = engine._load_state(baseline)
                fence.wait_database(u, state['ctx']['hengxin-vps-codex-worker'])
            return recover_or_refuse(u, expected_schema, restore_original,
                                     lambda: engine._quiesce(engine._load_state(engine._read('prepared.json'))))
        if external_fence is not None:
            fence.assert_held(u, external_fence)
            return checked_recover()
        with fence.hold(u):
            return checked_recover()

    changes = dict(RELEASE=backend, APPS=tuple(dict.fromkeys((*u.APPS, *scopes.UI.values()))),
                   contexts=contexts, validate_release=validate_release, probe_candidate=probe_candidate,
                   candidate_compose=lambda value: config.candidate(value, u, backend, frontend_paths),
                   stop_apps=stop_and_migrate, start_apps=start)
    with ExitStack() as stack:
        if gateway:
            changes.update(app_command=gateway.app_command, health=gateway.health)
        stack.enter_context(scopes.replace(u, **changes))
        stack.enter_context(scopes.replace(engine, prepare=prepare, _check=check, recover=guarded_recover))
        if gateway:
            stack.enter_context(scopes.replace(engine, _restore_sockets=lambda state: None))
            stack.enter_context(scopes.replace(engine, _quiesce=lambda state: gateway.seal()))
            stack.enter_context(scopes.replace(scope_snapshot, verify_frontend=gateway.verify_frontend))
        yield gateway
