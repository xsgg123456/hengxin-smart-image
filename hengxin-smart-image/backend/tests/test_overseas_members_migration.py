import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text

from test_overseas_database import BACKEND, disposable_databases, migrate, migration_environment


def test_upgrade_existing_members_preserves_status_roles_and_defaults_version(disposable_databases):
    url, _ = disposable_databases
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
                             'upgrade', 'overseas_0002'], cwd=BACKEND, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    ids = [uuid4(), uuid4()]
    try:
        with engine.begin() as connection:
            assert 'version' not in {c['name'] for c in inspect(connection).get_columns('overseas_members')}
            for member_id, status in zip(ids, ('pending', 'active')):
                connection.execute(text('INSERT INTO overseas_members '
                    '(id,corp_id,provider_user_id,name,department,status,created_at,updated_at) '
                    'VALUES (:id,\'corp\',:provider,\'海外成员\',\'部门\',:status,now(),now())'),
                    {'id': member_id, 'provider': str(member_id), 'status': status})
            connection.execute(text('INSERT INTO overseas_member_roles '
                '(id,user_id,role,created_at,updated_at) VALUES (:id,:user,\'designer\',now(),now())'),
                {'id': uuid4(), 'user': ids[1]})
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        with engine.connect() as connection:
            rows = connection.execute(text('SELECT id,status,version FROM overseas_members')).all()
            assert set(rows) == {(ids[0], 'pending', 1), (ids[1], 'active', 1)}
            assert connection.execute(text('SELECT user_id,role FROM overseas_member_roles')).all() == [
                (ids[1], 'designer')]
            assert connection.execute(text('SELECT count(*) FROM overseas_member_audits')).scalar() == 0
    finally:
        engine.dispose()
