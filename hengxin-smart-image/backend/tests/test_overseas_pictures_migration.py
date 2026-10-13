"""Frozen 0008 upgrade keeps all prior execution/material rows and domestic DB unchanged."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from sqlalchemy import MetaData, create_engine
from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND
from test_overseas_plans_postgres import plan_pg
from test_overseas_members_postgres import pg_factory


def test_frozen_migration_not_live_metadata(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0008_pictures.py'
    spec = importlib.util.spec_from_file_location('pictures_0008', path)
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
            assert {'overseas_pictures', 'overseas_picture_versions', 'overseas_archives'} <= set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def test_0007_upgrade_repeatable(disposable_databases):
    overseas_url, domestic_url = disposable_databases
    env = migration_environment(overseas_url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0007'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    before = snapshot(overseas_url)[1]
    domestic_before = snapshot(domestic_url)
    for _ in range(2):
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        after = snapshot(overseas_url)[1]
        assert after['overseas_plans'] == []
        assert after['overseas_alembic_version'] == [('overseas_0010',)]
        for table, rows in before.items():
            if table != 'overseas_alembic_version':
                assert after[table] == rows
        assert snapshot(domestic_url) == domestic_before


def test_frozen_upgrade_backfills_existing_confirmed_jobs(tmp_path):
    from uuid import uuid4
    import json
    from sqlalchemy import text
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0008_pictures.py'
    spec = importlib.util.spec_from_file_location('pictures_backfill', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    task, plan, job = uuid4(), uuid4(), uuid4()
    engine = create_engine('sqlite:///' + str(tmp_path / 'old.db'))
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE overseas_jobs (id TEXT, task_id TEXT, kind TEXT, payload TEXT)'))
            payload = {'planId': str(plan), 'sku': {'code': 'EXISTING', 'pictures': [{'title': '原有图'}]}}
            connection.execute(text('INSERT INTO overseas_jobs VALUES (:id,:task,:kind,:payload)'),
                {'id': str(job), 'task': str(task), 'kind': 'generation', 'payload': json.dumps(payload)})
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
            rows = connection.execute(text('SELECT sku, position, title, version FROM overseas_pictures')).all()
            assert rows == [('EXISTING', 0, '原有图', 0)]
    finally:
        engine.dispose()


def test_offline_backfill_sql_recreates_confirmed_slots_on_postgres(plan_pg):
    from sqlalchemy import delete, select, text
    from app.overseas.auth.models import Member
    from app.overseas.plans.service import confirm
    from app.overseas.plans.schemas import ConfirmRequest
    from app.overseas.pictures.models import Picture
    factory, actor, task, plan = plan_pg
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0008_pictures.py'
    spec = importlib.util.spec_from_file_location('pictures_offline', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with factory() as session:
        confirm(session, session.get(Member, actor), task, plan, ConfirmRequest(version=4), 'confirm')
    with factory.begin() as session:
        session.execute(delete(Picture))
        session.execute(text(migration.BACKFILL_SQL))
        session.execute(text(migration.BACKFILL_SQL))
        pictures = session.scalars(select(Picture)).all()
        assert len(pictures) == 2
        assert all(p.version == 0 and p.plan_id == plan and p.task_id == task for p in pictures)
