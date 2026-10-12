import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, inspect, text
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_0008_upgrade_seed_nullable_usage_and_domestic_unchanged(disposable_databases):
    overseas, domestic = disposable_databases
    env = migration_environment(overseas)
    command = [sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0008']
    result = subprocess.run(command, cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    from app.overseas.auth.models import Member
    from app.overseas.tasks.models import Task
    from app.overseas.execution.models import Job
    actor, task, job = uuid4(), uuid4(), uuid4()
    engine = create_engine(overseas)
    try:
        with engine.begin() as connection:
            connection.execute(Member.__table__.insert().values(id=actor, corp_id='legacy',
                provider_user_id='legacy', name='legacy', status='active'))
            connection.execute(Task.__table__.insert().values(id=task, name='legacy', product_name='p',
                brand='b', market='US', platform='Amazon', created_by=actor, designer_id=actor))
            connection.execute(Job.__table__.insert().values(id=job, task_id=task, kind='analysis',
                dedupe_key='legacy', payload={'skill': {'name': 'old', 'files': {'SKILL.md': 'old'}}}))
    finally:
        engine.dispose()
    before, domestic_before = snapshot(overseas), snapshot(domestic)
    for _ in range(2):
        result = migrate(env)
        assert result.returncode == 0, result.stderr
    after = snapshot(overseas)
    assert after[1]['overseas_alembic_version'] == [('overseas_0009',)]
    assert len(after[1]['overseas_settings']) == 1
    assert snapshot(domestic) == domestic_before
    for name, rows in before[1].items():
        if name == 'overseas_jobs':
            assert after[1][name] == [(*row, None) for row in rows]
        elif name != 'overseas_alembic_version':
            assert after[1][name] == rows
    engine = create_engine(overseas)
    try:
        assert next(c for c in inspect(engine).get_columns('overseas_jobs') if c['name'] == 'usage')['nullable']
    finally:
        engine.dispose()


def test_complete_offline_sql_executes_on_empty_postgres(disposable_databases):
    overseas, _ = disposable_databases
    result = migrate(migration_environment(overseas), 'alembic.overseas.ini', '--sql')
    assert result.returncode == 0, result.stderr
    engine = create_engine(overseas)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(result.stdout)
            connection.commit()
        with engine.connect() as connection:
            assert connection.execute(text('SELECT version FROM overseas_settings')).scalar_one() == 1
            assert connection.execute(text('SELECT version_num FROM overseas_alembic_version')).scalar_one() == 'overseas_0009'
    finally:
        engine.dispose()
