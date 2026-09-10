import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from app.models import Base


def test_archive_migration_repeatable_preserves_upstream():
    path = Path(__file__).parents[1] / 'migrations/versions/0007_archives.py'
    spec = importlib.util.spec_from_file_location('migration_archives', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    names = {model.__tablename__ for model in migration.TABLES}
    upstream = [table for table in Base.metadata.sorted_tables if table.name not in names]
    try:
        Base.metadata.create_all(engine, tables=upstream)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                for model in migration.TABLES:
                    assert {c['name'] for c in inspect(connection).get_columns(model.__tablename__)} == set(model.__table__.columns.keys())
                assert len(inspect(connection).get_foreign_keys('archive_images')) == 3
                migration.downgrade()
                assert set(inspect(connection).get_table_names()) == {t.name for t in upstream}
    finally:
        engine.dispose()
