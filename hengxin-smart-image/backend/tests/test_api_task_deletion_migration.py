import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_deletion_receipt_migration_is_idempotent_and_never_enqueues_history():
    path = Path(__file__).parents[1] / 'migrations' / 'versions' / '0029_api_task_deletions.py'
    spec = importlib.util.spec_from_file_location('deletion_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE api_image_tasks (id text, deleted_at text)'))
        connection.execute(text("INSERT INTO api_image_tasks VALUES ('old', '2026-01-01')"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        assert inspect(connection).has_table('api_task_deletions')
        assert connection.scalar(text('SELECT count(*) FROM api_task_deletions')) == 0
        assert connection.scalar(text('SELECT count(*) FROM api_image_tasks')) == 1
        migration.downgrade()
        assert inspect(connection).has_table('api_task_deletions')
    engine.dispose()
