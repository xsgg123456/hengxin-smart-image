import importlib
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


migration = importlib.import_module('migrations.versions.0034_domestic_studio_skill_states')


def test_migration_adds_empty_skill_state_without_touching_existing_tables():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE protected_data (value TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO protected_data VALUES ('preserved')"))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.upgrade()
            with pytest.raises(RuntimeError, match='manual verification'):
                migration.upgrade()
        assert inspect(connection).has_table('domestic_studio_skill_states')
        assert connection.scalar(text('SELECT count(*) FROM domestic_studio_skill_states')) == 0
        assert connection.scalar(text('SELECT value FROM protected_data')) == 'preserved'
    engine.dispose()


def test_incompatible_preexisting_table_is_not_overwritten():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE domestic_studio_skill_states (unrelated TEXT)'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            with pytest.raises(RuntimeError, match='manual verification'):
                migration.upgrade()
        assert [column['name'] for column in inspect(connection).get_columns('domestic_studio_skill_states')] == ['unrelated']
    engine.dispose()
