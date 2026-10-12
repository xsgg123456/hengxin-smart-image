"""Frozen execution migration is replayable and keeps existing task data."""
import importlib.util
from pathlib import Path
from uuid import uuid4
from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, inspect, select
from types import SimpleNamespace


def test_frozen_migration_replay_and_seed():
    path = Path(__file__).parents[1] / 'migrations/overseas/versions/0006_execution.py'
    spec = importlib.util.spec_from_file_location('execution_0006', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    metadata = MetaData()
    tasks = Table('overseas_tasks', metadata, Column('id', Uuid, primary_key=True))
    identity = uuid4()
    try:
        with engine.begin() as connection:
            tasks.create(connection)
            connection.execute(tasks.insert().values(id=identity))
            module.op = SimpleNamespace(get_bind=lambda: connection)
            module.context = SimpleNamespace(is_offline_mode=lambda: False)
            module.upgrade()
            module.upgrade()
            assert connection.execute(select(tasks.c.id)).scalar_one() == identity
            metadata.reflect(connection)
            gate = metadata.tables['overseas_execution_gate']
            row = connection.execute(select(gate)).one()
            assert row.id == 1 and row.paused is False
            assert set(inspect(connection).get_table_names()) == {
                'overseas_tasks', 'overseas_execution_gate', 'overseas_jobs',
                'overseas_job_outbox', 'overseas_execution_events'}
            assert 'process_exited' in {item['name'] for item in inspect(connection).get_columns('overseas_jobs')}
    finally:
        engine.dispose()
