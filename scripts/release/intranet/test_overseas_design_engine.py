"""Failure boundaries on the overseas side of the shared migration coordinator."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import domestic_tasks_engine as coordinator
import domestic_tasks_release as release
import engine
import overseas_design_engine as migration
import overseas_design_policy as policy
import snapshot


def test_owner_command_checks_database_identity(monkeypatch):
    monkeypatch.setattr(snapshot, 'database', lambda *a: ('wrong', 'postgres', 'hengxin_overseas'))
    with pytest.raises(RuntimeError, match='identity'):
        migration.psql(object())


def test_sql_generation_must_match_pinned_revision_output(tmp_path):
    calls = []
    def native(ctx, **kwargs):
        calls.append(kwargs)
        return 'BEGIN; SELECT 1; COMMIT;'
    with pytest.raises(RuntimeError, match='differs'):
        migration.render(SimpleNamespace(RELEASE=tmp_path, native_run=native), object(), policy)
    assert calls[0]['code'] == migration.VALIDATE
    assert calls[1]['args'] == ('-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0026:overseas_0028', '--sql')


def test_failed_handshake_cannot_send_migration(monkeypatch):
    from io import BytesIO
    stdin = BytesIO()
    proc = SimpleNamespace(stdin=stdin, kill=Mock(), communicate=Mock())
    from contextlib import nullcontext
    monkeypatch.setattr(migration, 'psql', lambda u: ['psql'])
    monkeypatch.setattr(migration, 'render', lambda *args: 'CREATE TABLE never_sent();')
    monkeypatch.setattr(migration.subprocess, 'Popen', lambda *a, **k: nullcontext(proc))
    monkeypatch.setattr(migration, 'wait_ready', Mock(side_effect=RuntimeError('connection interrupted')))
    with pytest.raises(RuntimeError, match='interrupted'):
        migration.run_migration(object(), {}, 91, policy)
    assert migration.LOCK.encode() in stdin.getvalue()
    assert b'CREATE TABLE' not in stdin.getvalue()
    proc.kill.assert_called_once()
    proc.communicate.assert_called_once_with()


def test_engine_operates_only_on_overseas_worker_and_schema(tmp_path, monkeypatch):
    before = {'schema': {'domestic': '0046', 'overseas': policy.SOURCE}, 'data': {'pg':'retained'}}
    schema = dict(before['schema'])
    def save(name, value, **kwargs):
        (tmp_path/name).write_text(json.dumps(value))
    u = SimpleNamespace(WORK=tmp_path, data_identity=lambda: before['data'])
    monkeypatch.setattr(engine, '_save', save)
    monkeypatch.setattr(engine, '_read', lambda name: json.loads((tmp_path/name).read_bytes()))
    monkeypatch.setattr(coordinator.fence, 'assert_held', lambda *a: None)
    monkeypatch.setattr(coordinator, 'stopped', lambda *a: None)
    monkeypatch.setattr(snapshot, 'schemas', lambda u: dict(schema))
    monkeypatch.setattr(policy.history, 'capture', lambda u: {'rows': 4})
    verify = Mock()
    monkeypatch.setattr(policy.history, 'verify', verify)
    backup = Mock(return_value='digest')
    monkeypatch.setattr(policy.history, 'backup', backup)
    worker = {'group': 'overseas'}
    def run(u, ctx, descriptor, transition):
        assert ctx is worker and descriptor == 91 and transition is policy
        schema['overseas'] = policy.TARGET
    monkeypatch.setattr(migration, 'run_migration', run)
    coordinator.migrate(u, {'hengxin-overseas-worker': worker}, before, 91, policy)
    assert schema == {'overseas': policy.TARGET, 'domestic': '0046'}
    verify.assert_called_once_with(u, {'rows': 4})
    backup.assert_called_with(u, 91)
    coordinator.check_migration(u, before, 91, policy)
    verify.assert_called_once()


def test_design_commands_reject_any_other_scope():
    for scope,mode in [('shared','full'),('domestic','full'),('overseas','frontend')]:
        with pytest.raises(RuntimeError, match='--scope overseas'):
            release.run(None, SimpleNamespace(scope=scope, mode=mode), policy)


def test_preflight_registers_every_candidate_model_before_database_inspection():
    import ast
    env = Path(__file__).resolve().parents[3] / 'hengxin-smart-image/backend/migrations/overseas/env.py'
    if not env.exists():
        pytest.skip('The separate tools installation does not carry the application source')
    models = {node.module.removeprefix('app.overseas.') + '.' + name.name
              for node in ast.parse(env.read_text(encoding='utf-8')).body
              if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('app.overseas.')
              for name in node.names if name.name in ('models', 'application_models')}
    assert len(models) >= 13 and set(migration.MODELS) == models
    registered, steps = [], []
    from contextlib import nullcontext
    connection = SimpleNamespace(exec_driver_sql=lambda sql: steps.append(sql))
    def validate(value):
        assert value is connection and set(registered) == {'app.overseas.' + model for model in models}
        assert steps == ['SET TRANSACTION READ ONLY']
        steps.append('validated')
    def load(name, *args, **kwargs):
        if name == 'importlib':
            return SimpleNamespace(import_module=registered.append)
        assert name == 'app.overseas.db'
        return SimpleNamespace(require_overseas_context=lambda: None, validate_migration_database=validate,
                               get_engine=lambda: SimpleNamespace(connect=lambda: nullcontext(connection)))
    exec(migration.VALIDATE, {'__builtins__': {'__import__': load}})
    assert steps[-1] == 'validated'


def test_forward_recovery_keeps_domestic_publisher_with_live_full_compose(tmp_path, monkeypatch):
    import scopes
    u = SimpleNamespace(WORK=tmp_path, COMPOSE=tmp_path / 'compose.json', RELEASE=tmp_path / 'candidate',
                        NATIVE={}, APPS=(*scopes.APPS['overseas'], scopes.UI['overseas']),
                        ENTRIES=('overseas-api', 'overseas-ui'), run=Mock(), start_apps=Mock(),
                        validate_release=lambda: 'manifest', digest=lambda data: 'digest', write=Mock())
    u.COMPOSE.write_text(json.dumps({'services': {name: {} for name in (*u.APPS, scopes.DOMESTIC_PUBLISHER)}}))
    controls = []
    def control(action, names):
        controls.append((action, tuple(names), tuple(u.APPS)))
    u.app_command = control
    (tmp_path / 'compose.candidate.json').write_text('{}')
    monkeypatch.setattr(engine, 'u', u)
    monkeypatch.setattr(engine, '_read', lambda path: {'release_manifest': 'manifest'})
    monkeypatch.setattr(engine, '_load_state', lambda baseline: {'ctx': {}, 'phase':'stopping'})
    for name in ('_check', '_quiesce', '_phase', '_save'):
        monkeypatch.setattr(engine, name, Mock())
    for name in ('check_migration','freeze','stopped'):
        monkeypatch.setattr(coordinator, name, Mock())
    coordinator.resume({'before': {}}, 91, policy)
    assert controls == [('stop', u.ENTRIES, u.APPS), ('stop', ('overseas-skill-publisher',), u.APPS)]
    u.start_apps.assert_called_once_with({})
