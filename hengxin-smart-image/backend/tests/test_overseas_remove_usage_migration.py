import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_removes_existing_usage_preserving_job_and_other_tables_and_repeats():
    path = Path(__file__).resolve().parents[1] / 'migrations/overseas/versions/0016_remove_job_usage.py'
    spec = importlib.util.spec_from_file_location('remove_usage', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE overseas_jobs (id INTEGER PRIMARY KEY, payload JSON, usage JSON)'))
            connection.execute(text("INSERT INTO overseas_jobs VALUES (1, :payload, :usage)"),
                               {"payload": "{}", "usage": '{"input_tokens":100}'})
            connection.execute(text('CREATE TABLE domestic_jobs (usage JSON)'))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()
            assert [col['name'] for col in inspect(connection).get_columns('overseas_jobs')] == ['id', 'payload']
            assert connection.execute(text('SELECT * FROM overseas_jobs')).all() == [(1, '{}')]
            assert [col['name'] for col in inspect(connection).get_columns('domestic_jobs')] == ['usage']
    finally:
        engine.dispose()
