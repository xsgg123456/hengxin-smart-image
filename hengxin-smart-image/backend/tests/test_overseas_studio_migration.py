"""Exercise populated 0014 -> 0015 on a disposable PostgreSQL database."""
from datetime import datetime, timezone
import runpy
import subprocess
import sys
import pytest
from uuid import uuid4
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, Table, select, inspect, func
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_0014_history_survives_repeatable_transcript_migration(disposable_databases):
    url, domestic = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0014'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    owner, task_id, channel_id, job_id, turn_id, picture_id = [uuid4() for _ in range(6)]
    times = dict(created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    reply = '# 历史完整回复\n' + '原文' * 4000
    names = ['overseas_members', 'overseas_tasks', 'overseas_jobs', 'overseas_studio_conversations',
             'overseas_studio_turns', 'overseas_studio_pictures']
    try:
        with engine.begin() as conn:
            md = MetaData()
            tables = {name: Table(name, md, autoload_with=conn) for name in names}
            conn.execute(tables['overseas_members'].insert().values(id=owner, corp_id='test',
                provider_user_id=str(owner), name='设计', department='', status='active', version=1, **times))
            conn.execute(tables['overseas_tasks'].insert().values(id=task_id, name='历史任务',
                product_name='产品', brand='品牌', platform='Amazon', market='US', remarks='',
                created_by=owner, designer_id=owner, status='studio', version=1,
                requirements_approved=True, workflow='studio', **times))
            conn.execute(tables['overseas_studio_conversations'].insert().values(id=channel_id,
                task_id=task_id, session_id='old-cli-thread', **times))
            conn.execute(tables['overseas_jobs'].insert().values(id=job_id, task_id=task_id,
                kind='studio', dedupe_key='old', payload={}, status='succeeded', version=1,
                process_exited=True, cancel_requested=False, execution_count=1, **times))
            conn.execute(tables['overseas_studio_turns'].insert().values(id=turn_id, task_id=task_id,
                conversation_id=channel_id, job_id=job_id, actor_id=owner, text='历史输入', reply=reply,
                attachment_ids=[], reference_ids=[], dispatched=True, **times))
            conn.execute(tables['overseas_studio_pictures'].insert().values(id=picture_id,
                task_id=task_id, turn_id=turn_id, name='old.png', content_type='image/png',
                size_bytes=100, checksum='a' * 64, bucket='test', object_key='old/file', width=10, height=10, **times))
        before, domestic_before = snapshot(url)[1], snapshot(domestic)
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0015_studio_transcript.py'))['upgrade']()
            md = MetaData()
            tables = {name: Table(name, md, autoload_with=conn) for name in names}
            for name, table in tables.items():
                row = conn.execute(select(table)).one()
                assert tuple(row)[:len(before[name][0])] == before[name][0]
            transcript = Table('overseas_studio_transcript', md, autoload_with=conn)
            rows = conn.execute(select(transcript)).mappings().all()
            assert len(rows) == 1 and rows[0]['text'] == reply and rows[0]['turn_id'] == turn_id
            assert rows[0]['created_at'] == times['created_at']
            turn = conn.execute(select(tables['overseas_studio_turns'])).mappings().one()
            assert turn['event_offset'] == 0 and not turn['event_invalid'] and turn['delivery_error'] is None
            conn.execute(tables['overseas_studio_conversations'].insert().values(id=uuid4(),
                task_id=task_id, **times))
            assert conn.scalar(select(func.count()).select_from(tables['overseas_studio_conversations'])) == 2
            assert not inspect(conn).get_unique_constraints('overseas_studio_conversations')
            with pytest.raises(RuntimeError, match='forward-only'):
                runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0015_studio_transcript.py'))['downgrade']()
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
