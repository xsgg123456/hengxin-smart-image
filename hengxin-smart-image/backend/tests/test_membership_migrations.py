"""Real previous-head upgrade and rollback retain every historical member ID."""
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text

from test_overseas_database import BACKEND, disposable_databases, migration_environment, migrate


@pytest.mark.integration
@pytest.mark.parametrize('business', ['domestic', 'overseas'])
def test_pending_classification_and_additive_schema_rollback(disposable_databases, business):
    overseas_url, domestic_url = disposable_databases
    overseas = business == 'overseas'
    url = overseas_url if overseas else domestic_url
    config = 'alembic.overseas.ini' if overseas else 'alembic.ini'
    previous = 'overseas_0013' if overseas else '0027'
    current = 'overseas_0014' if overseas else '0028'
    table = 'overseas_members' if overseas else 'users'
    version_table = 'overseas_alembic_version' if overseas else 'alembic_version'
    env = migration_environment(url, business)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', config, 'upgrade', previous],
        cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr
    ids = {status: uuid4() for status in ('active', 'pending', 'disabled')}
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            for status, member_id in ids.items():
                columns = 'corp_id, provider_user_id, department, version' if overseas else 'identity_source, role'
                values = "'corp', :identity, '', 1" if overseas else "'dingtalk', NULL"
                connection.execute(text(f'INSERT INTO {table} '
                    f'(id, name, status, created_at, updated_at, {columns}) '
                    f'VALUES (:id, :name, :status, now(), now(), {values})'),
                    {'id': member_id, 'name': '历史成员', 'identity': str(member_id), 'status': status})
            before = [tuple(row) for row in connection.execute(text(f'SELECT * FROM {table} ORDER BY id'))]
        result = migrate(env, config)
        assert result.returncode == 0, result.stderr
        with engine.connect() as connection:
            rows = dict(connection.execute(text(f'SELECT id, directory_state FROM {table}')).all())
            assert rows == {ids['active']: 'enrolled', ids['disabled']: 'enrolled',
                            ids['pending']: 'legacy_unconfirmed'}
            assert connection.scalar(text(f'SELECT version_num FROM {version_table}')) == current
            assert connection.scalar(text(f'SELECT count(*) FROM {business}_membership_applications')) == 0
            assert connection.scalar(text(f'SELECT count(*) FROM {business}_membership_application_events')) == 0
        result = subprocess.run([sys.executable, '-m', 'alembic', '-c', config, 'downgrade', previous],
            cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
        assert result.returncode == 0, result.stderr
        with engine.connect() as connection:
            assert 'directory_state' not in {col['name'] for col in inspect(connection).get_columns(table)}
            assert [tuple(row) for row in connection.execute(text(f'SELECT * FROM {table} ORDER BY id'))] == before
        assert migrate(env, config).returncode == 0
    finally:
        engine.dispose()
