"""Populated 0016 upgrades without rewriting the original or historical records."""
from datetime import datetime, timezone
import runpy
import subprocess
import sys
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, Table, inspect, select
from test_overseas_database import disposable_databases, migration_environment, snapshot, BACKEND, migrate


def test_visibility_migration_preserves_populated_duplicates_and_is_repeatable(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0016'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    actor, task, conversation, job, turn, material = [uuid4() for _ in range(6)]
    uploads = [uuid4(), uuid4()]
    times = dict(created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    names = ['overseas_members', 'overseas_tasks', 'overseas_materials', 'overseas_studio_uploads',
             'overseas_studio_conversations', 'overseas_jobs', 'overseas_studio_turns']
    try:
        with engine.begin() as conn:
            md = MetaData()
            tables = {name: Table(name, md, autoload_with=conn) for name in names}
            conn.execute(tables['overseas_members'].insert().values(id=actor, corp_id='test',
                provider_user_id=str(actor), name='设计', department='', status='active', version=1, **times))
            conn.execute(tables['overseas_tasks'].insert().values(id=task, name='历史任务', product_name='产品',
                brand='品牌', platform='Amazon', market='US', remarks='', created_by=actor, designer_id=actor,
                status='studio', version=1, requirements_approved=True, workflow='studio', **times))
            asset = dict(task_id=task, name='original.txt', content_type='text/plain', size_bytes=10,
                         checksum='a' * 64, bucket='test', **times)
            conn.execute(tables['overseas_materials'].insert().values(**asset, id=material, owner_id=actor,
                kind='competitor', status='ready', version=0, object_key='original'))
            for index, identity in enumerate(uploads):
                conn.execute(tables['overseas_studio_uploads'].insert().values(**asset, id=identity,
                    object_key=f'upload/{index}'))
            conn.execute(tables['overseas_studio_conversations'].insert().values(id=conversation,
                task_id=task, session_id='untouched-cli', **times))
            conn.execute(tables['overseas_jobs'].insert().values(id=job, task_id=task, kind='studio',
                dedupe_key='history', payload={'inputs': [{'id': str(uploads[1]), 'checksum': 'a' * 64}]},
                status='succeeded', version=1, process_exited=True, cancel_requested=False, execution_count=1, **times))
            conn.execute(tables['overseas_studio_turns'].insert().values(id=turn, task_id=task,
                conversation_id=conversation, job_id=job, actor_id=actor, text='历史原件',
                attachment_ids=['task:' + str(material), 'upload:' + str(uploads[1])], reference_ids=[],
                dispatched=True, **times))
        before, domestic_before = snapshot(url)[1], snapshot(domestic)
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        migration = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0017_studio_material_visibility.py'))
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration['upgrade']()
            visibility = Table('overseas_studio_material_visibility', MetaData(), autoload_with=conn)
            assert conn.execute(select(visibility)).all() == []
            conn.execute(visibility.insert().values(id=uuid4(), task_id=task, checksum='a' * 64,
                                                  hidden=True, **times))
            assert any(c['column_names'] == ['task_id', 'checksum']
                       for c in inspect(conn).get_unique_constraints(visibility.name))
        after = snapshot(url)[1]
        assert all(after[name] == rows for name, rows in before.items() if name != 'overseas_alembic_version')
        assert snapshot(domestic) == domestic_before
        with pytest.raises(RuntimeError, match='forward-only'):
            migration['downgrade']()
    finally:
        engine.dispose()
