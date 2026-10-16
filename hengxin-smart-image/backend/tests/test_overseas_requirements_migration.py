"""Production 0009 -> 0010 keeps all in-flight work, grants no new draft bypass."""
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from test_overseas_database import disposable_databases, migration_environment, snapshot, BACKEND


def test_0009_upgrade_preserves_tasks_jobs_and_materials(disposable_databases):
    overseas, domestic = disposable_databases
    env = migration_environment(overseas)
    command = [sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', 'overseas_0009']
    result = subprocess.run(command, cwd=BACKEND, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    engine = create_engine(overseas)
    states = ('created', 'submitted', 'analyzing', 'plan', 'generating', 'review', 'archived')
    ids = {state: uuid4() for state in states}
    actor = uuid4()
    now = datetime.now(timezone.utc)
    metadata = MetaData()
    metadata.reflect(engine)
    try:
        with engine.begin() as connection:
            connection.execute(metadata.tables['overseas_members'].insert().values(id=actor,
                corp_id='test', provider_user_id='legacy', name='旧成员', department='', status='active',
                version=1, created_at=now, updated_at=now))
            connection.execute(metadata.tables['overseas_member_roles'].insert().values(id=uuid4(),
                user_id=actor, role='designer', created_at=now, updated_at=now))
            for state, identity in ids.items():
                connection.execute(metadata.tables['overseas_tasks'].insert().values(id=identity,
                    name=state, product_name='商品', brand='品牌', platform='Amazon', market='US', remarks='',
                    created_by=actor, designer_id=actor, status=state, version=8, created_at=now, updated_at=now))
            material = uuid4()
            connection.execute(metadata.tables['overseas_materials'].insert().values(id=material,
                owner_id=actor, task_id=ids['analyzing'], kind='competitor', name='original.csv',
                bucket='overseas-test', object_key='legacy-original', content_type='text/csv',
                checksum='a' * 64, size_bytes=10, status='ready', version=1, created_at=now, updated_at=now))
            from app.overseas.execution.models import Job
            connection.execute(Job.__table__.insert().values(id=uuid4(), task_id=ids['analyzing'],
                kind='analysis', dedupe_key='legacy-inflight', payload={'materials': [{'id': str(material)}]}))
        before, domestic_before = snapshot(overseas)[1], snapshot(domestic)
        for _ in range(2):
            result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                'upgrade', 'overseas_0010'], cwd=BACKEND, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        with engine.connect() as connection:
            tasks = Table('overseas_tasks', MetaData(), autoload_with=connection)
            for row in connection.execute(select(tasks)).mappings():
                assert row['id'] == ids[row['status']] and row['version'] == 8
                assert row['requirements_approved'] == (row['status'] != 'created')
                assert row['material_ids'] is None
            constraints = inspect(connection).get_unique_constraints('overseas_materials')
            assert not any(c['column_names'] == ['task_id', 'kind'] for c in constraints)
            assert connection.execute(text('SELECT count(*) FROM overseas_jobs')).scalar_one() == 1
        # Compare all original columns as well as the new review gate above.
        # In-flight payload/state and every other historical row must remain exact.
        with engine.connect() as connection:
            for name, original in metadata.tables.items():
                if name == 'overseas_alembic_version':
                    continue
                after = [tuple(row) for row in connection.execute(select(original))]
                assert sorted(before[name], key=repr) == sorted(after, key=repr), name
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
