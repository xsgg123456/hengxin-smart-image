"""Upgrade Phase18 data in disposable databases; preserve domestic snapshot."""
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_upgrade_0003_preserves_members_and_domestic(disposable_databases):
    overseas_url, domestic_url = disposable_databases
    domestic = migrate(migration_environment(domestic_url, 'domestic'), 'alembic.ini')
    assert domestic.returncode == 0, domestic.stderr
    before_domestic = snapshot(domestic_url)
    env = migration_environment(overseas_url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                             'upgrade', 'overseas_0003'], cwd=BACKEND, env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    identifier, role_id = uuid4(), uuid4()
    engine = create_engine(overseas_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO overseas_members (id,corp_id,provider_user_id,name,department,status,version,created_at,updated_at) "
                "VALUES (:id,'test','preserved','保留成员','设计','active',3,now(),now())"), {'id': identifier})
            connection.execute(text("INSERT INTO overseas_member_roles (id,user_id,role,created_at,updated_at) "
                "VALUES (:id,:user,'designer',now(),now())"), {'id': role_id, 'user': identifier})
        before = snapshot(overseas_url)[1]
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        after = snapshot(overseas_url)[1]
        for table in ('overseas_members', 'overseas_member_roles', 'overseas_sessions', 'overseas_member_audits'):
            assert after[table] == before[table]
        for table in ('overseas_tasks', 'overseas_task_skus', 'overseas_task_events', 'overseas_task_requests', 'overseas_task_outbox'):
            assert after[table] == []
        assert after['overseas_alembic_version'] == [('overseas_0010',)]
        assert snapshot(domestic_url) == before_domestic
    finally:
        engine.dispose()
