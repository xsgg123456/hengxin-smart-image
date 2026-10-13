"""Current application metadata is exercised against isolated SQLite only."""
import ast
from pathlib import Path
import sys

import pytest

from conftest import seed
from member_audit import audit
from member_catalog import BUSINESSES, engine_for
from member_codec import read_json
from member_reconcile import reconcile
from member_restore import restore
from test_member_maintenance import approve


@pytest.mark.parametrize('business', ['domestic', 'overseas'])
def test_current_business_models_round_trip_and_reference_inventory(tmp_path, monkeypatch, business):
    backend = Path(__file__).resolve().parents[3] / 'hengxin-smart-image' / 'backend'
    monkeypatch.syspath_prepend(str(backend))
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('HX_BUSINESS_CONTEXT', business)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + (tmp_path / 'unused-app.sqlite').as_posix())
    monkeypatch.setenv('MINIO_ACCESS_KEY', 'test-access-key')
    monkeypatch.setenv('MINIO_SECRET_KEY', 'test-secret-key')
    env = backend / 'migrations' / ('overseas/env.py' if business == 'overseas' else 'env.py')
    syntax = ast.parse(env.read_text(encoding='utf-8-sig'))
    # Register exactly the migration's models without running migration/config code.
    imports = [node for node in syntax.body if isinstance(node, ast.ImportFrom)
               and node.module and node.module.startswith('app.')
               and node.module not in ('app.core.config', 'app.db.session')]
    imports += [node for node in syntax.body if isinstance(node, ast.ImportFrom) and node.module == 'app']
    scope = {}
    exec(compile(ast.Module(body=imports, type_ignores=[]), '<isolated-model-imports>', 'exec'), scope)
    base = scope['Base']
    engine = engine_for('sqlite:///' + (tmp_path / 'real-models.sqlite').as_posix())
    try:
        base.metadata.create_all(engine)
        names = BUSINESSES[business]
        tables = {key: base.metadata.tables[name] for key, name in zip(
            ('member', 'roles', 'sessions', 'applications'), names)}
        if business == 'domestic':
            tables['identities'] = base.metadata.tables['user_identities']
        seed(engine, tables, business)
        before = audit(engine, business)
        assert before['members'][0]['cleanupEligible']
        inventory = before['referenceInventory']
        assert len(inventory) > 10
        if business == 'overseas':
            assert any(item['table'] == 'main.overseas_archives' and item['kind'] == 'identity_column' for item in inventory)
        else:
            assert any(item['columns'] == ['request_operator_id'] for item in inventory)
        result = reconcile(engine, business, approve(before), apply=True, recovery_dir=tmp_path / 'recovery')
        assert result['results'][0]['outcome'] == 'deleted'
        bundle = read_json(result['results'][0]['recoveryFile'])
        assert restore(engine, business, bundle, apply=True)['outcome'] == 'restored'
        assert audit(engine, business)['members'] == before['members']
    finally:
        engine.dispose()
