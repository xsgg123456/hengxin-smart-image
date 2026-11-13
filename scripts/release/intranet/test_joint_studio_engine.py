"""Failure boundaries for a backup-bound forward-only schema switch."""
import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

import pytest

import engine
import joint_studio_engine as joint
import joint_studio_forward as forward
import joint_studio_ingress as ingress
import snapshot
import test_engine


@pytest.fixture
def migration(tmp_path, monkeypatch):
    data = {'domestic-postgres': 'same', 'overseas-postgres': 'same'}
    schemas = {'domestic': '0032', 'overseas': 'overseas_0026'}
    actions = []
    def write(path, content, mode=0o600, exclusive=False):
        with open(path, 'xb' if exclusive else 'wb') as stream:
            stream.write(content)
    u = SimpleNamespace(WORK=tmp_path, RELEASE=tmp_path / 'release', ENTRIES=('api',),
                        safe=lambda path: None, write=write, digest=lambda raw: hashlib.sha256(raw).hexdigest(),
                        data_identity=lambda: data.copy(), app_command=lambda *args: actions.append(args))
    monkeypatch.setattr(joint.fence, 'hold', lambda u: nullcontext(99))
    def backup(_, work, pass_fds=()):
        assert pass_fds == (99,)
        actions.append('backup')
        root = work / 'data-backup'
        root.mkdir()
        receipt = {}
        for side in ('domestic', 'overseas', 'accounts_config'):
            value = (side + '-private-test-data').encode()
            filename = side + '.dump' if side != 'accounts_config' else 'accounts-config.tar'
            (root / filename).write_bytes(value)
            digest = hashlib.sha256(value).hexdigest()
            receipt[side] = {'bytes': len(value), 'sha256': digest} if side != 'accounts_config' else digest
        (root / 'verified.json').write_text(json.dumps(receipt))
    def native_run(ctx, module, cwd, args, timeout, pass_fds=()):
        assert pass_fds == (99,) and ctx['env']['DOMESTIC_STUDIO_MIGRATION_FENCE'] == '1'
        actions.append(('alembic', args, ctx['env']['DOMESTIC_STUDIO_PROTECTED']))
        schemas['domestic'] = '0043'
    u.native_run = native_run
    monkeypatch.setattr(joint.operations, 'backup', backup)
    monkeypatch.setattr(snapshot, 'schemas', lambda _: schemas.copy())
    ctx = {'hengxin-vps-codex-worker': {'env': {}}}
    return u, ctx, data, schemas, actions


def test_verified_backup_precedes_migration_and_supports_forward_recovery(migration):
    u, ctx, data, schemas, actions = migration
    joint.migrate(u, ctx, data, schemas.copy())
    assert actions == ['backup', ('alembic', ('upgrade', '0043'), '1')]
    assert schemas == {'domestic': '0043', 'overseas': 'overseas_0026'}
    joint.check_migration(u, {'data_containers': data}, 'overseas_0026')
    (u.WORK / 'data-backup/domestic.dump').write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='backup'):
        joint.check_migration(u, {'data_containers': data}, 'overseas_0026')


def test_backup_drift_refuses_before_schema_command(migration, monkeypatch):
    u, ctx, data, schemas, actions = migration
    def bad_backup(*args, **kwargs):
        (u.WORK / 'data-backup').mkdir()
        (u.WORK / 'data-backup/verified.json').write_text('{}')
    monkeypatch.setattr(joint.operations, 'backup', bad_backup)
    with pytest.raises(RuntimeError, match='backup'):
        joint.migrate(u, ctx, data, schemas.copy())
    assert schemas['domestic'] == '0032' and actions == []


def test_only_unchanged_schema_can_use_original_recovery(migration):
    u, _, _, schemas, actions = migration
    expected = schemas.copy()
    assert joint.recover_or_refuse(u, expected, lambda: 'recovered') == 'recovered'
    schemas['domestic'] = '0043'
    with pytest.raises(RuntimeError, match='forward recovery'):
        joint.recover_or_refuse(u, expected, lambda: pytest.fail('must not restore old code'))
    assert actions == [('stop', ('api',))]


@pytest.fixture
def interrupted(tmp_path, monkeypatch):
    work, systemd = tmp_path / 'work', tmp_path / 'systemd'
    work.mkdir()
    systemd.mkdir()
    names = ('worker', 'deletions')
    for name in names:
        (systemd / (name + '.service.d')).mkdir()
        (work / (name + '.conf')).write_bytes(('new-' + name).encode())
    (work / 'compose.candidate.json').write_bytes(b'{"services": {}}')
    compose = tmp_path / 'compose.json'
    compose.write_bytes(b'{"services": {}}')
    baseline = {'release_manifest': 'verified', 'data_containers': {'db': 'same'}}
    state = {'phase': 'stopping', 'ctx': {}, 'paused': [], 'sockets': []}
    actions = []
    def write(path, data, mode=0o600, exclusive=False):
        Path(path).write_bytes(data)
        actions.append(('write', Path(path).name))
    u = SimpleNamespace(WORK=work, SYSTEMD=systemd, DROPIN='90-unified-source.conf',
        COMPOSE=compose, NATIVE={n: 'module' for n in names}, ENTRIES=('api',),
        APPS=('api', 'worker'), safe=lambda path: None, write=write,
        app_command=lambda *args: actions.append(args), validate_release=lambda: 'verified',
        start_apps=lambda ctx: actions.append('start'))
    monkeypatch.setattr(engine, 'u', u)
    monkeypatch.setattr(engine, '_read', lambda name: baseline)
    monkeypatch.setattr(engine, '_load_state', lambda value: state)
    monkeypatch.setattr(engine, '_check', lambda *args, **kwargs: actions.append('check'))
    monkeypatch.setattr(engine, '_quiesce', lambda value: actions.append('drain'))
    monkeypatch.setattr(engine, '_restore_sockets', lambda value: actions.append('restore-sockets'))
    monkeypatch.setattr(engine, '_phase', lambda value, phase: value.update(phase=phase))
    monkeypatch.setattr(engine, '_save', lambda name, value, exclusive=False: actions.append(('save', name)))
    monkeypatch.setattr(joint, 'check_migration', lambda *args: actions.append('migration-check'))
    monkeypatch.setattr(forward, 'stop_existing', lambda u: actions.append('stop-existing'))
    return u, state, actions


def test_forward_resume_drains_and_installs_only_candidate(interrupted):
    u, state, actions = interrupted
    assert forward.resume('overseas_0026') == 'applied'
    assert actions.index('drain') < actions.index('stop-existing') < actions.index('start')
    assert u.COMPOSE.read_bytes() == (u.WORK / 'compose.candidate.json').read_bytes()
    assert ('save', 'applied.json') in actions
    assert state['phase'] == 'starting'


def test_failed_forward_start_keeps_ingress_closed(interrupted):
    u, _, actions = interrupted
    def fail(ctx):
        raise RuntimeError('startup failure')
    u.start_apps = fail
    with pytest.raises(RuntimeError, match='startup'):
        forward.resume('overseas_0026')
    assert actions.count(('stop', ('api',))) == 2
    assert ('save', 'applied.json') not in actions


def test_invalid_phase_is_rejected_before_runtime_mutation(interrupted):
    _, state, actions = interrupted
    state['phase'] = 'ingress'
    with pytest.raises(RuntimeError, match='phase'):
        forward.resume('overseas_0026')
    assert actions == []


class BeforeMigrationRecoveryTests(unittest.TestCase):
    def setUp(self):
        test_engine.EngineTests.setUp(self)
        self.gates = {'ingress': True, 'workers': True}
        for name, replacement in (
                ('gate_state', lambda u, name: self.gates[name]),
                ('set_gate', lambda u, name, opened: self.gates.update({name: opened}))):
            patcher = patch.object(joint.paths, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_original_recovery_does_not_repeat_failed_migration_or_start_publisher(self):
        u = engine.u
        expected = {'domestic': '0032', 'overseas': 'overseas_0026'}
        frontends = {name: u.RELEASE for name in ('domestic', 'overseas', 'shared')}
        failure = Mock(side_effect=RuntimeError('migration failure'))
        with patch.object(joint.paths, 'identities'), patch.object(joint.config, 'candidate', return_value={'new': True}), \
             patch.object(joint.config, 'native_dropin', return_value=b'[Service]\n'), \
             patch.object(u, 'compose'), patch.object(u, 'native_run'), \
             patch.object(joint.fence, 'hold', return_value=nullcontext(99)), \
             patch.object(snapshot, 'schemas', return_value=expected), patch.object(joint, 'migrate', failure):
            for path in self.work.iterdir():
                path.unlink()
            with joint.context(u.RELEASE, frontends, expected):
                engine.prepare()
                with self.assertRaisesRegex(RuntimeError, 'migration failure'):
                    engine.apply()
            self.assertEqual(failure.call_count, 1)
            self.assertEqual(self.mocks['stop_apps'].call_count, 2)
            self.assertEqual(self.mocks['start_apps'].call_count, 1)
            self.assertTrue((self.work / 'rolled-back.json').exists())

    def test_schema_committed_start_failure_never_restores_old_code(self):
        u = engine.u
        expected = {'domestic': '0032', 'overseas': 'overseas_0026'}
        actual = expected.copy()
        frontends = {name: u.RELEASE for name in ('domestic', 'overseas', 'shared')}
        def migrate(*args):
            actual['domestic'] = '0043'
        self.mocks['start_apps'].side_effect = RuntimeError('startup failed')
        with patch.object(joint.paths, 'identities'), patch.object(joint.config, 'candidate', return_value={'new': True}), \
             patch.object(joint.config, 'native_dropin', return_value=b'[Service]\n'), \
             patch.object(u, 'compose'), patch.object(u, 'native_run'), \
             patch.object(joint.fence, 'hold', return_value=nullcontext(99)), \
             patch.object(snapshot, 'schemas', side_effect=lambda value: actual.copy()), \
             patch.object(joint, 'migrate', side_effect=migrate):
            for path in self.work.iterdir():
                path.unlink()
            with joint.context(u.RELEASE, frontends, expected):
                engine.prepare()
                with self.assertRaisesRegex(RuntimeError, 'RECOVERY_UNCONFIRMED'):
                    engine.apply()
            self.assertEqual(actual['domestic'], '0043')
            self.assertFalse((self.work / 'rolled-back.json').exists())
            self.assertEqual(self.compose.read_bytes(), (self.work / 'compose.candidate.json').read_bytes())
            self.assertEqual(self.mocks['app_command'].call_args.args, ('stop', u.ENTRIES))

    def test_joint_apply_keeps_private_gateway_and_does_not_restore_socket(self):
        u = engine.u
        expected = {'domestic': '0032', 'overseas': 'overseas_0026'}
        frontends = {name: u.RELEASE for name in ('domestic', 'overseas', 'shared')}
        events = []
        endpoint = self.work / 'credential-socket-test'
        def gate(sockets):
            sockets.append((endpoint, endpoint.stat().st_ino, 0o600))
            endpoint.chmod(0)
        self.mocks['gate_accounts'].side_effect = gate
        with patch.object(joint.paths, 'identities'), patch.object(joint.config, 'candidate', return_value={'new': True}), \
             patch.object(joint.config, 'native_dropin', return_value=b'[Service]\n'), \
             patch.object(u, 'compose'), patch.object(u, 'native_run'), patch.object(joint, 'migrate'), \
             patch.object(engine, '_quiesce', side_effect=lambda _: events.append('paused')), \
             patch.object(ingress.PrivateIngress, 'start',
                          lambda self, original, ctx: self.app_command('up', u.ENTRIES)), \
             patch.object(ingress.PrivateIngress, 'stage', side_effect=lambda names: events.append(('private', tuple(names)))), \
             patch.object(ingress.PrivateIngress, 'health'), \
             patch.object(joint.fence, 'hold', return_value=nullcontext(99)), \
             patch.object(snapshot, 'schemas', return_value=expected):
            for path in self.work.iterdir():
                path.unlink()
            with joint.context(u.RELEASE, frontends, expected):
                engine.prepare()
                endpoint.write_text('isolated gate')
                endpoint.chmod(0o600)
                self.assertEqual(engine.apply(), 'applied')
            self.assertEqual(events, [('private', tuple(u.ENTRIES))])
            self.assertEqual(endpoint.stat().st_mode & 0o777, 0)
            self.assertTrue((self.work / 'applied.json').exists())
