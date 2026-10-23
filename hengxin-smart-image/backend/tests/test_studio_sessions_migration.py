"""Populated PostgreSQL 0020→0021 retains bytes, IDs and over-cap history."""
from datetime import datetime, timezone
from uuid import uuid4
import runpy
import subprocess
import sys
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, Table, select, inspect
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_populated_sessions_migrate_repeatably_without_changing_history(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0020'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    now = dict(created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    actor, task, job, turn, picture, archive, upload = [uuid4() for _ in range(7)]
    channels = sorted([uuid4() for _ in range(12)])
    names = ['overseas_members', 'overseas_tasks', 'overseas_jobs', 'overseas_studio_conversations',
        'overseas_studio_turns', 'overseas_studio_uploads', 'overseas_studio_pictures',
        'overseas_archives', 'overseas_archive_assets', 'overseas_studio_material_visibility']
    try:
        with engine.begin() as connection:
            metadata = MetaData()
            tables = {name: Table(name, metadata, autoload_with=connection) for name in names}
            def insert(table_name, **values):
                connection.execute(tables[table_name].insert().values(**values, **now))
            insert('overseas_members', id=actor, corp_id='test', provider_user_id=str(actor),
                name='历史设计师', department='', status='active', version=1)
            insert('overseas_tasks', id=task, name='历史多会话', product_name='商品', brand='品牌',
                platform='Amazon', market='US', remarks='', created_by=actor, designer_id=actor,
                status='studio', workflow='studio', version=2, requirements_approved=True)
            for identity in channels:
                insert('overseas_studio_conversations', id=identity, task_id=task, session_id=str(identity))
            insert('overseas_jobs', id=job, task_id=task, kind='studio', dedupe_key='history', payload={},
                status='succeeded', version=1, process_exited=True, cancel_requested=False, execution_count=1)
            insert('overseas_studio_uploads', id=upload, task_id=task, name='历史输入.txt', content_type='text/plain',
                size_bytes=100, checksum='a' * 64, bucket='test', object_key='studio/uploads/history')
            insert('overseas_studio_turns', id=turn, task_id=task, conversation_id=channels[0], job_id=job,
                actor_id=actor, text='历史原话', reply='历史回复', attachment_ids=['upload:' + str(upload)],
                reference_ids=[], dispatched=True, event_offset=0, event_invalid=False)
            image = dict(name='历史图片.png', content_type='image/png', size_bytes=200, checksum='b' * 64,
                bucket='test', width=10, height=20)
            insert('overseas_studio_pictures', id=picture, task_id=task, turn_id=turn,
                object_key='studio/pictures/history', sku='A', **image)
            insert('overseas_archives', id=archive, task_id=task, versions=['studio:' + str(picture)])
            insert('overseas_archive_assets', id=uuid4(), archive_id=archive, source_version='studio:' + str(picture),
                position=0, sku='A', object_key='archives/independent', **image)
            insert('overseas_studio_material_visibility', id=uuid4(), task_id=task, checksum='a' * 64, hidden=True)
            original = {name: connection.execute(select(table)).mappings().all() for name, table in tables.items()}
        domestic_before = snapshot(domestic)
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        with engine.begin() as connection:
            metadata = MetaData()
            tables = {name: Table(name, metadata, autoload_with=connection) for name in names}
            for name, rows in original.items():
                after = {row['id']: row for row in connection.execute(select(tables[name])).mappings()}
                assert len(after) == len(rows)
                for row in rows:
                    assert all(after[row['id']][field] == value for field, value in row.items())
            migrated = connection.execute(select(tables['overseas_studio_conversations']).order_by(
                tables['overseas_studio_conversations'].c.id)).mappings().all()
            assert [row['name'] for row in migrated] == [f'会话 {i + 1}' for i in range(12)]
            assert all(row['version'] == 1 for row in migrated)
            assert connection.execute(select(tables['overseas_studio_uploads'])).mappings().one()['conversation_id'] is None
            asset = connection.execute(select(tables['overseas_archive_assets'])).mappings().one()
            assert asset['source_conversation_id'] == channels[0] and asset['source_conversation_name'] == '会话 1'
            connection.execute(tables['overseas_studio_conversations'].update().where(
                tables['overseas_studio_conversations'].c.id == channels[0]).values(name='用户重命名'))
            with Operations.context(MigrationContext.configure(connection)):
                runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0021_studio_sessions.py'))['upgrade']()
            assert connection.scalar(select(tables['overseas_studio_conversations'].c.name).where(
                tables['overseas_studio_conversations'].c.id == channels[0])) == '用户重命名'
            assert any(c['column_names'] == ['task_id', 'checksum', 'scope'] for c in
                inspect(connection).get_unique_constraints('overseas_studio_material_visibility'))
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
