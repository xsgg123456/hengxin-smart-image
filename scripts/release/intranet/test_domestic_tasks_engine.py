"""Failure injection for backup, migration and forward-only source switching."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import domestic_tasks_engine as tasks
import engine
import snapshot
import test_engine


@pytest.fixture
def migration(tmp_path, monkeypatch):
    schema = {'domestic': '0043', 'overseas': 'overseas_0026'}
    before = {'schema': schema.copy(), 'data': {'postgres': 'same'}}
    actions = []
    def write(path, content, **kwargs):
        with path.open('xb' if kwargs.get('exclusive') else 'wb') as stream:
            stream.write(content)
    u = SimpleNamespace(WORK=tmp_path, RELEASE=tmp_path / 'candidate', safe=lambda p: None,
                        digest=snapshot.sha, write=write, data_identity=lambda: before['data'])
    monkeypatch.setattr(engine, 'u', u)
    monkeypatch.setattr(tasks.fence, 'assert_held', lambda *a: None)
    monkeypatch.setattr(tasks, 'stopped', lambda u: actions.append('stopped'))
    monkeypatch.setattr(snapshot, 'schemas', lambda u: schema.copy())
    def backup(u, work, scope, pass_fds):
        assert scope == 'domestic' and pass_fds == (99,)
        actions.append('backup')
        folder = work / 'data-backup'
        folder.mkdir()
        (folder / 'domestic.dump').write_bytes(b'verified-test-backup')
        (folder / 'verified.json').write_text(json.dumps({'domestic': {
            'bytes': 20, 'sha256': snapshot.sha(b'verified-test-backup')}}))
    monkeypatch.setattr(tasks.operations, 'backup', backup)
    monkeypatch.setattr(tasks.history, 'capture', lambda u: {'rows': 'same'})
    monkeypatch.setattr(tasks.history, 'verify', lambda u, expected: actions.append('history-verified'))
    def native(ctx, **kwargs):
        assert kwargs['args'] == ('upgrade', '0044') and kwargs['pass_fds'] == (99,)
        assert ctx['env']['DOMESTIC_STUDIO_MIGRATION_FENCE'] == '1'
        actions.append('migration')
        schema['domestic'] = '0044'
    u.native_run = native
    return u, before, schema, actions


def test_backup_and_stopped_history_precede_single_migration(migration):
    u, before, schema, actions = migration
    tasks.migrate(u, {'hengxin-vps-codex-worker': {'env': {}}}, before, 99)
    assert actions == ['stopped', 'backup', 'migration', 'stopped', 'history-verified']
    assert schema == dict(before['schema'], domestic='0044')
    assert engine._read('tasks-migration.json')['phase'] == 'migrated'
    tasks.check_migration(u, before, 99)
    assert actions.count('migration') == 1
    (u.WORK / 'data-backup/domestic.dump').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError, match='backup'):
        tasks.check_migration(u, before, 99)


def test_backup_failure_never_migrates(migration, monkeypatch):
    u, before, schema, actions = migration
    monkeypatch.setattr(tasks.operations, 'backup', Mock(side_effect=RuntimeError('disk full')))
    with pytest.raises(RuntimeError, match='disk full'):
        tasks.migrate(u, {'hengxin-vps-codex-worker': {'env': {}}}, before, 99)
    assert schema == before['schema'] and actions == ['stopped']
    assert not (u.WORK / 'tasks-migration.json').exists()


def test_commit_before_parent_receipt_recovers_without_rerunning_migration(migration, monkeypatch):
    u, before, schema, actions = migration
    original = u.native_run
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('parent interrupted after commit')
    u.native_run = interrupted
    with pytest.raises(RuntimeError, match='interrupted'):
        tasks.migrate(u, {'hengxin-vps-codex-worker': {'env': {}}}, before, 99)
    assert engine._read('tasks-migration.json')['phase'] == 'migrating'
    tasks.check_migration(u, before, 99)
    assert engine._read('tasks-migration.json')['phase'] == 'migrated'
    assert actions.count('migration') == 1


def test_history_mismatch_keeps_committed_migration_pending(migration, monkeypatch):
    u, before, schema, actions = migration
    monkeypatch.setattr(tasks.history, 'verify', Mock(side_effect=RuntimeError('history differs')))
    with pytest.raises(RuntimeError, match='history differs'):
        tasks.migrate(u, {'hengxin-vps-codex-worker': {'env': {}}}, before, 99)
    assert schema['domestic'] == '0044'
    assert engine._read('tasks-migration.json')['phase'] == 'migrating'


class TaskEngineFailures(test_engine.EngineTests):
    def test_committed_schema_never_restores_original_source(self):
        u = engine.u
        before = {'schema': {'domestic': '0043', 'overseas': '0026'}}
        schema = before['schema'].copy()
        def migrate(*args):
            schema['domestic'] = '0044'
        with patch.object(tasks, 'freeze'), patch.object(tasks, 'check_restarts'), \
             patch.object(tasks, 'migrate', side_effect=migrate), \
             patch.object(tasks.fence, 'assert_held'), \
             patch.object(snapshot, 'schemas', side_effect=lambda _: schema.copy()), \
             patch.object(u, 'start_apps', side_effect=RuntimeError('new start failed')):
            with tasks.context({'before': before}, 99):
                with pytest.raises(RuntimeError, match='RECOVERY_UNCONFIRMED'):
                    engine.apply()
        assert self.compose.read_bytes() == self.new
        assert not (self.work / 'rolled-back.json').exists()
        assert (self.work / 'started.json').exists()

    def test_precommit_failure_restores_old_code(self):
        u = engine.u
        before = {'schema': {'domestic': '0043', 'overseas': '0026'}}
        with patch.object(tasks, 'freeze'), patch.object(tasks, 'check_restarts'), \
             patch.object(tasks, 'migrate', side_effect=RuntimeError('migration rolled back')), \
             patch.object(tasks.fence, 'assert_held'), \
             patch.object(snapshot, 'schemas', return_value=before['schema']):
            with tasks.context({'before': before}, 99):
                with pytest.raises(RuntimeError, match='migration rolled back'):
                    engine.apply()
        assert self.compose.read_bytes() == self.old
        assert (self.work / 'rolled-back.json').exists()

    def test_forward_resume_installs_only_candidate_after_commit(self):
        u = engine.u
        before = {'schema': {'domestic': '0043', 'overseas': '0026'}}
        state = dict(prepared=u.digest((self.work / 'prepared.json').read_bytes()),
                     phase='stopping', ctx=self.ctx, paused=[], sockets=[])
        engine._save('started.json', state)
        with patch.object(tasks, 'check_migration'), patch.object(tasks, 'freeze'), \
             patch.object(tasks, 'stopped'), patch.object(tasks.forward, 'stop_existing'), \
             patch.object(engine, '_quiesce'):
            tasks.resume({'before': before}, 99)
        assert self.compose.read_bytes() == self.new
        assert (self.work / 'applied.json').exists()
        assert not (self.work / 'rolled-back.json').exists()
