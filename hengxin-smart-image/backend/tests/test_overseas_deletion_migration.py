"""Historical archive metadata survives real 0012 -> 0013 PostgreSQL migration."""
from datetime import datetime, timezone
import runpy
import subprocess
import sys
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, Table, select, inspect
from app.overseas.db import SCHEMA_REVISION
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_0012_archives_backfill_and_repeatable_upgrade(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    command = [sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0012']
    result = subprocess.run(command, cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    owner, designer, task_id, archive_id = [uuid4() for _ in range(4)]
    versions = [str(uuid4()), 'studio:' + str(uuid4())]
    times = dict(created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    try:
        with engine.begin() as connection:
            md = MetaData()
            for name in ('overseas_members', 'overseas_tasks', 'overseas_task_skus', 'overseas_archives'):
                Table(name, md, autoload_with=connection)
            for identity in (owner, designer):
                connection.execute(md.tables['overseas_members'].insert().values(id=identity,
                    corp_id='test', provider_user_id=str(identity), name='归属', department='',
                    status='active', version=1, **times))
            connection.execute(md.tables['overseas_tasks'].insert().values(id=task_id, name='旧任务',
                product_name='原品名', brand='原品牌', platform='Amazon', market='US', remarks='private',
                created_by=owner, designer_id=designer, status='archived', version=1,
                requirements_approved=True, workflow='legacy', **times))
            connection.execute(md.tables['overseas_task_skus'].insert().values(id=uuid4(), task_id=task_id,
                code='旧SKU', code_key='旧sku', position=0, **times))
            connection.execute(md.tables['overseas_archives'].insert().values(id=archive_id,
                task_id=task_id, versions=versions, **times))
        domestic_before = snapshot(domestic)
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        with engine.begin() as connection:
            path = BACKEND / 'migrations/overseas/versions/0013_task_deletion_archives.py'
            with Operations.context(MigrationContext.configure(connection)):
                runpy.run_path(str(path))['upgrade']()
            archive = Table('overseas_archives', MetaData(), autoload_with=connection)
            row = connection.execute(select(archive)).mappings().one()
            assert row['versions'] == versions and row['task_id'] == task_id
            assert row['product_name'] == '原品名' and row['brand'] == '原品牌'
            assert row['skus'] == [{'code': '旧SKU'}] and row['sku_search'] == '旧SKU'
            assert row['created_by'] == owner and row['designer_id'] == designer
            assert row['created_at'] == times['created_at']
            assert next(c for c in inspect(connection).get_columns('overseas_archives')
                if c['name'] == 'task_id')['nullable']
            assert {'overseas_task_deletions', 'overseas_execution_objects', 'overseas_archive_assets'} <= set(
                inspect(connection).get_table_names())
        assert snapshot(url)[1]['overseas_alembic_version'] == [(SCHEMA_REVISION,)]
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
