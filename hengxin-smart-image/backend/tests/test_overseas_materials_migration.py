"""Phase19 tasks and idempotency survive a repeatable frozen Phase20 upgrade."""
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_upgrade_0004_preserves_existing_tasks(disposable_databases):
    overseas_url, domestic_url = disposable_databases
    env = migration_environment(overseas_url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                             'upgrade', 'overseas_0004'], cwd=BACKEND, env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(overseas_url)
    actor, task = uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO overseas_members (id,corp_id,provider_user_id,name,department,status,version,created_at,updated_at) "
                "VALUES (:id,'test','preserved','保留成员','设计','active',1,now(),now())"), {'id': actor})
            connection.execute(text("INSERT INTO overseas_tasks (id,name,product_name,brand,platform,market,remarks,created_by,designer_id,status,version,created_at,updated_at) "
                "VALUES (:id,'旧图需','产品','品牌','Amazon','美国','备注',:actor,:actor,'created',1,now(),now())"),
                {'id': task, 'actor': actor})
            connection.execute(text("INSERT INTO overseas_task_requests (id,user_id,operation,target,key,body_hash,task_id,created_at,updated_at) "
                "VALUES (:id,:actor,'create','','old-key',:hash,:task,now(),now())"),
                {'id': uuid4(), 'actor': actor, 'task': task, 'hash': 'a' * 64})
        before = snapshot(overseas_url)[1]
        assert 'overseas_materials' not in before
        for _ in range(2):
            result = migrate(env)
            assert result.returncode == 0, result.stderr
            after = snapshot(overseas_url)[1]
            for table, rows in before.items():
                if table != 'overseas_alembic_version':
                    assert after[table] == rows
            assert after['overseas_alembic_version'] == [('overseas_0009',)]
            assert after['overseas_materials'] == after['overseas_material_versions'] == []
    finally:
        engine.dispose()
