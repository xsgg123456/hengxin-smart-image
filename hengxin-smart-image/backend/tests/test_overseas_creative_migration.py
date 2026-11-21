"""Real 0028 -> 0029 migration with existing records and frozen creator metadata."""
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import MetaData, create_engine, inspect, text
from test_overseas_database import BACKEND, disposable_databases, migration_environment, snapshot


def test_migrate_populated_0028_without_backfill(disposable_databases):
    url, domestic = disposable_databases
    def migrate(revision):
        result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                                 'upgrade', revision], cwd=BACKEND, env=migration_environment(url),
                                capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr

    domestic_before = snapshot(domestic)
    migrate('overseas_0028')
    engine = create_engine(url)
    actor, task_id, archive_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    times = dict(created_at=now, updated_at=now)
    try:
        with engine.begin() as con:
            md = MetaData()
            md.reflect(con)
            con.execute(md.tables['overseas_members'].insert().values(id=actor, corp_id='company',
                provider_user_id='one', name='A', department='', status='active', **times))
            con.execute(md.tables['overseas_member_roles'].insert().values(id=uuid4(), user_id=actor,
                role='designer', **times))
            con.execute(md.tables['overseas_tasks'].insert().values(id=task_id, created_by=actor, designer_id=actor,
                name='existing', product_name='lamp', brand='OUTON', platform='Amazon', market='', remarks='',
                status='studio', version=1, workflow='studio', **times))
            con.execute(md.tables['overseas_archives'].insert().values(id=archive_id, task_id=task_id,
                versions=['existing.png'], task_name='existing', **times))
        before = snapshot(url)[1]
        migrate('head')
        after = snapshot(url)[1]
        for table in before.keys() - {'overseas_alembic_version', 'overseas_tasks', 'overseas_archives'}:
            assert after[table] == before[table], table
        assert after['overseas_tasks'] == [before['overseas_tasks'][0] + (None, None)]
        assert after['overseas_archives'] == [before['overseas_archives'][0] + (None,)]
        assert after['overseas_tool_skill_bindings'] == []
        with engine.begin() as con:
            con.execute(text("UPDATE overseas_member_roles SET role='non_designer' WHERE user_id=:id"), {'id': actor})
            fk, = inspect(con).get_foreign_keys('overseas_tool_skill_bindings')
            assert fk['referred_table'] == 'overseas_installed_skill_availability'
            assert fk['options']['ondelete'] == 'CASCADE'
        assert snapshot(domestic) == domestic_before
    finally:
        engine.dispose()
