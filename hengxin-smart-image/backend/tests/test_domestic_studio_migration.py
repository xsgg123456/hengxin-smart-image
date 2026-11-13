import importlib
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


migration = importlib.import_module('migrations.versions.0033_domestic_studio_bindings')


def test_upgrade_refuses_existing_table_and_preserves_unrelated_data():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE protected_data (value VARCHAR(20) NOT NULL)'))
        connection.execute(text("INSERT INTO protected_data VALUES ('preserved')"))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.upgrade()
            with pytest.raises(RuntimeError, match='manual verification'):
                migration.upgrade()
        assert inspect(connection).has_table('domestic_studio_skill_bindings')
        assert connection.scalar(text('SELECT value FROM protected_data')) == 'preserved'
        assert connection.scalar(text('SELECT count(*) FROM domestic_studio_skill_bindings')) == 0
    engine.dispose()


def test_unexpected_existing_table_is_rejected():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE domestic_studio_skill_bindings (unexpected TEXT)'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            with pytest.raises(RuntimeError, match='manual verification'):
                migration.upgrade()
    engine.dispose()
