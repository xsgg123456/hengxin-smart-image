"""Real PostgreSQL 0024 -> 0025: truthful snapshots, retry, and domestic isolation."""
from datetime import datetime, timezone
import runpy
import subprocess
import sys
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import MetaData, create_engine, select, text
from test_overseas_database import BACKEND, disposable_databases, migration_environment, migrate, snapshot


@pytest.mark.integration
def test_language_upgrade_preserves_history_and_only_backfills_known_sources(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0024'], cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    actor, task_id, linked_id, detached_id = [uuid4() for _ in range(4)]
    times = dict(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    try:
        with engine.begin() as connection:
            md = MetaData()
            md.reflect(connection)
            connection.execute(md.tables['overseas_members'].insert().values(id=actor,
                corp_id='test', provider_user_id=str(actor), name='历史成员', department='',
                status='active', version=1, directory_state='enrolled', **times))
            connection.execute(md.tables['overseas_tasks'].insert().values(id=task_id,
                name='真实历史任务名', product_name='商品', brand='品牌', platform='Amazon',
                market='US', remarks='原始备注', created_by=actor, designer_id=actor,
                workflow='studio', status='archived', version=9, requirements_approved=True, **times))
            for identity, source in ((linked_id, task_id), (detached_id, None)):
                connection.execute(md.tables['overseas_archives'].insert().values(id=identity,
                    task_id=source, versions=[], product_name='商品', brand='品牌', platform='Amazon',
                    skus=[{'code': 'A'}], sku_search='A', created_by=actor, designer_id=actor, **times))
        original, domestic_before = snapshot(url), snapshot(domestic)
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        with engine.begin() as connection:
            for name, table in md.tables.items():
                if name != 'overseas_alembic_version':
                    assert sorted(map(tuple, connection.execute(select(table))), key=repr) == sorted(original[1][name], key=repr)
            assert connection.execute(text('SELECT language FROM overseas_tasks')).scalar_one() is None
            rows = {r.id: r for r in connection.execute(text('SELECT id, task_name, language FROM overseas_archives'))}
            assert rows[linked_id].task_name == '真实历史任务名' and rows[linked_id].language is None
            assert rows[detached_id].task_name is None and rows[detached_id].language is None
            # Simulate retry after columns exist, and protect independently captured values.
            connection.execute(text("UPDATE overseas_tasks SET language='fr', name='修改后名称'"))
            migration = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0025_requirement_language.py'))
            with Operations.context(MigrationContext.configure(connection)):
                migration['upgrade']()
                connection.execute(text("UPDATE overseas_tasks SET language='de'"))
                migration['upgrade']()
            row = connection.execute(text('SELECT task_name, language FROM overseas_archives WHERE id=:id'), {'id': linked_id}).one()
            assert row.task_name == '真实历史任务名' and row.language == 'fr'
            detached = connection.execute(text('SELECT task_name, language FROM overseas_archives WHERE id=:id'), {'id': detached_id}).one()
            assert detached.task_name is None and detached.language is None
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
