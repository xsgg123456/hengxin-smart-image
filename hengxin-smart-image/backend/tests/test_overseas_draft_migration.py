"""0026 adds only draft tables and retains all 0025 history."""
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_draft_migration_offline_additive():
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0025:overseas_0026', '--sql'], cwd=BACKEND,
        env=migration_environment('postgresql+psycopg://fake:fake@localhost:1/fake_test'),
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for name in ('overseas_requirement_drafts', 'overseas_draft_materials', 'overseas_draft_imports'):
        assert f'CREATE TABLE IF NOT EXISTS {name}' in result.stdout
    assert 'ON DELETE SET NULL' in result.stdout
    assert 'DROP TABLE' not in result.stdout and 'ALTER TABLE overseas_tasks' not in result.stdout


def test_upgrade_0025_retains_history(disposable_databases):
    url, _ = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0025'], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text('''INSERT INTO overseas_members
                (id,corp_id,provider_user_id,name,department,status,version,directory_state,created_at,updated_at)
                VALUES (:id,'test','draft-history','保留用户','设计','active',1,'enrolled',now(),now())'''),
                {'id': uuid4()})
        before = snapshot(url)[1]
        for _ in range(2):
            result = migrate(env)
            assert result.returncode == 0, result.stderr
            after = snapshot(url)[1]
            for table, rows in before.items():
                if table != 'overseas_alembic_version':
                    assert after[table] == rows
            assert after['overseas_alembic_version'] == [('overseas_0026',)]
            assert after['overseas_requirement_drafts'] == after['overseas_draft_imports'] == after['overseas_draft_materials'] == []
    finally:
        engine.dispose()
