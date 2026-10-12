"""Frozen 0007 upgrade keeps all prior execution/material rows and domestic DB unchanged."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from sqlalchemy import MetaData, create_engine
from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_frozen_migration_not_live_metadata(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0007_plans.py'
    spec = importlib.util.spec_from_file_location('plans_0007', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    from app.overseas.db import Base
    monkeypatch.setattr(Base, 'metadata', MetaData())
    engine = create_engine('sqlite:///' + str(tmp_path / 'migration.db'))
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
                migration.upgrade()
            from sqlalchemy import inspect
            assert 'overseas_plans' in inspect(connection).get_table_names()
    finally:
        engine.dispose()


def test_0006_upgrade_repeatable(disposable_databases):
    overseas_url, domestic_url = disposable_databases
    env = migration_environment(overseas_url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0006'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    before = snapshot(overseas_url)[1]
    domestic_before = snapshot(domestic_url)
    for _ in range(2):
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        after = snapshot(overseas_url)[1]
        assert after['overseas_plans'] == []
        assert after['overseas_alembic_version'] == [('overseas_0008',)]
        for table, rows in before.items():
            if table != 'overseas_alembic_version':
                assert after[table] == rows
        assert snapshot(domestic_url) == domestic_before
