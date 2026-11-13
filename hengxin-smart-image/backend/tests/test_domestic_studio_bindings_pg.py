"""Optional PostgreSQL transaction tests; accepts only a disposable *_test DB."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.execution.models import ExecutionGate
from app.modules.domestic_studio.bindings import freeze_for_send, lock_admission, read_bindings, save_bindings as save_checked
from app.modules.domestic_studio.models import WorkspaceBinding
from app.modules.domestic_studio.policy import WORKSPACES


@pytest.fixture
def database():
    raw_url = os.environ.get('TEST_DOMESTIC_STUDIO_DATABASE_URL')
    if not raw_url:
        pytest.skip('TEST_DOMESTIC_STUDIO_DATABASE_URL is required')
    url = make_url(raw_url)
    if url.drivername != 'postgresql+psycopg' or not (url.database or '').endswith('_test'):
        pytest.fail('PostgreSQL *_test database is required')
    base = create_engine(url, isolation_level='READ COMMITTED')
    schema = 'hx_studio_' + uuid4().hex
    with base.begin() as connection:
        assert schema not in inspect(connection).get_schema_names()
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = base.execution_options(schema_translate_map={None: schema})
    try:
        ExecutionGate.__table__.create(engine)
        WorkspaceBinding.__table__.create(engine)
        with Session(engine) as session:
            session.add(ExecutionGate(id=1))
            session.commit()
        yield engine
    finally:
        with base.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base.dispose()


def config(value):
    return dict.fromkeys(WORKSPACES) | {'camera': value}


def save_bindings(session, values, verify):
    return save_checked(session, values, verify, expected=read_bindings(session))


def frozen(identity):
    return {'skill': {'id': identity}}


def test_read_committed_refreshes_after_another_connection_commits(database):
    with Session(database) as first:
        save_bindings(first, config('old'), lambda _: None)
        first.commit()
        cached = first.get(WorkspaceBinding, 'camera')
        with Session(database) as second:
            assert first.connection().connection.driver_connection is not second.connection().connection.driver_connection
            save_bindings(second, config('new'), lambda _: None)
            second.commit()
        assert cached.skill_id == 'old'
        assert freeze_for_send(first, 'camera', None, frozen) == frozen('new')


def test_gate_serializes_bindings_and_execution(database):
    with Session(database) as first, Session(database) as second:
        lock_admission(first)
        second.execute(text("SET LOCAL lock_timeout = '250ms'"))
        with pytest.raises(OperationalError) as error:
            lock_admission(second)
        assert error.value.orig.sqlstate == '55P03'  # lock_not_available
        second.rollback()
        first.rollback()
        lock_admission(second)


def test_repeatable_read_is_refused_after_prior_snapshot(database):
    with Session(database) as seed:
        save_bindings(seed, config('old'), lambda _: None)
        seed.commit()
    repeatable = database.execution_options(isolation_level='REPEATABLE READ')
    with Session(repeatable) as first:
        assert first.get(WorkspaceBinding, 'camera').skill_id == 'old'
        with Session(database) as second:
            save_bindings(second, config('new'), lambda _: None)
            second.commit()
        with pytest.raises(RuntimeError, match='READ COMMITTED'):
            freeze_for_send(first, 'camera', None, frozen)


def test_autocommit_is_refused_even_when_server_reports_read_committed(database):
    autocommit = database.execution_options(isolation_level='AUTOCOMMIT')
    with Session(autocommit) as session:
        with pytest.raises(RuntimeError, match='transactional connections'):
            lock_admission(session)


def test_stale_administrator_cannot_overwrite_another_binding(database):
    from fastapi import HTTPException
    with Session(database) as first, Session(database) as second:
        original_first, original_second = read_bindings(first), read_bindings(second)
        save_checked(first, original_first | {'camera': 'camera-skill'}, lambda _: None, expected=original_first)
        first.commit()
        with pytest.raises(HTTPException) as error:
            save_checked(second, original_second | {'case': 'case-skill'}, lambda _: None, expected=original_second)
        assert error.value.status_code == 409
        second.rollback()
        assert read_bindings(second) == original_first | {'camera': 'camera-skill'}
