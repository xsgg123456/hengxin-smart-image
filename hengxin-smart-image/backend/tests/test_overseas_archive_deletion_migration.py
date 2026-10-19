"""A repeatable receipt migration does not remove existing archive business data."""
import runpy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_receipts_upgrade_idempotent_and_isolated(disposable_databases):
    url, domestic = disposable_databases
    before = snapshot(domestic)
    result = migrate(migration_environment(url))
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                upgrade = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0019_archive_deletion.py'))['upgrade']
                upgrade()
                upgrade()
            columns = {column['name'] for column in inspect(connection).get_columns('overseas_archive_deletions')}
            assert columns == {'archive_id', 'status', 'error', 'created_at', 'updated_at'}
            assert inspect(connection).get_foreign_keys('overseas_archive_deletions') == []
        assert snapshot(domestic) == before
    finally:
        engine.dispose()
