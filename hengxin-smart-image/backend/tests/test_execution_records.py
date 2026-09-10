"""Database guards for duplicate launches, shared sessions and missing observations."""
import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Base
from app.modules.tasks.attempts import (
    ExecutionAttempt, ExecutionSession, ExecutionUsage, WorkerHeartbeat,
)
from test_tasks import task_env, submit  # noqa: F401
from files_helpers import files_env  # noqa: F401


def attempt_for(receipt, operator_id, **overrides):
    return ExecutionAttempt(**{
        'round_id': UUID(receipt['roundId']), 'task_id': UUID(receipt['taskId']),
        'operator_id': operator_id, 'claim_token': uuid4(), 'node': 'test-node',
        'workspace': '/tasks/test/rounds/test', 'cli_version': '0.153.4', **overrides,
    })


def test_session_unique_across_tasks_and_nullable_before_launch(task_env):
    first = submit(task_env, key='first').json()
    second = submit(task_env, key='second').json()
    factory = task_env[1]
    with factory.begin() as session:
        session.add_all([ExecutionSession(task_id=UUID(item['taskId'])) for item in (first, second)])
    with factory.begin() as session:
        session.get(ExecutionSession, UUID(first['taskId'])).session_id = 'session-a'
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.get(ExecutionSession, UUID(second['taskId'])).session_id = 'session-a'
    with factory() as session:
        assert session.get(ExecutionSession, UUID(second['taskId'])).session_id is None
        assert session.get(ExecutionSession, UUID(first['taskId'])).session_id == 'session-a'


def test_redelivery_cannot_record_second_launch_or_duplicate_usage(task_env):
    receipt = submit(task_env).json()
    factory, operator = task_env[1], task_env[3][0]
    with factory.begin() as session:
        attempt = attempt_for(receipt, operator)
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id
        session.add(ExecutionUsage(attempt_id=attempt_id, data=None))
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(attempt_for(receipt, operator))
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(ExecutionUsage(attempt_id=attempt_id, data={'total_tokens': 123}))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionAttempt)) == 1
        attempt = session.get(ExecutionAttempt, attempt_id)
        assert attempt.status == 'starting' and attempt.process_id is None
        assert attempt.started_at and attempt.finished_at is None
        assert session.scalar(text('SELECT data IS NULL FROM execution_usage')) == 1


def test_attempt_rejects_invalid_status_and_missing_round(task_env):
    receipt = submit(task_env).json()
    factory, operator = task_env[1], task_env[3][0]
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(attempt_for(receipt, operator, status='queued'))
    with factory.begin() as session:
        session.execute(text('PRAGMA foreign_keys=ON'))
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(attempt_for(receipt, operator, round_id=uuid4()))


def test_migration_repeat_preserves_records_and_downgrade_is_repeatable(monkeypatch):
    migration_path = Path(__file__).parents[1] / 'migrations/versions/0006_execution.py'
    spec = importlib.util.spec_from_file_location('execution_migration', migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        monkeypatch.setattr(migration.op, 'get_bind', lambda: connection)
        migration.downgrade()
        migration.downgrade()
        migration.upgrade()
        connection.execute(WorkerHeartbeat.__table__.insert().values(node='worker-1', state='ready'))
        migration.upgrade()
        row = connection.execute(WorkerHeartbeat.__table__.select()).mappings().one()
        assert row['node'] == 'worker-1' and row['checked_at'] and row['dependencies'] == {}
        migration.downgrade()
        assert 'task_records' in inspect(connection).get_table_names()
        assert 'execution_attempts' not in inspect(connection).get_table_names()
    engine.dispose()
