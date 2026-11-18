"""0045 preserves every historical row and enforces the expanded domain on each table."""
import importlib
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from test_domestic_studio_bindings_pg import database

migration = importlib.import_module('migrations.versions.0045_domestic_workspaces')
PRODUCTS = ('camera', 'case', 'film', 'cable', 'earbud', 'accessory')
REPLACEMENTS = ('product', 'scene', 'phone', 'edit')
TABLES = ('domestic_studio_tasks', 'domestic_studio_conversations', 'domestic_studio_archives',
          'domestic_studio_workspaces', 'domestic_studio_skill_bindings')


def test_workspace_checks_expand_without_rewriting_rows_and_refuse_lossy_downgrade(database):
    schema = database.get_execution_options()['schema_translate_map'][None]
    with database.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        # Use the original anonymous inline CHECK shape so PostgreSQL names each constraint.
        connection.execute(text('DROP TABLE domestic_studio_skill_bindings'))
        for table in TABLES:
            old = ('camera', 'case') if table.endswith('_archives') else ('camera', 'case', 'product', 'scene', 'phone')
            connection.execute(text(f'CREATE TABLE {table} (workspace varchar(20) NOT NULL, '
                                    f'payload text NOT NULL, CHECK (workspace IN {old}))'))
            connection.execute(text(f'INSERT INTO {table} VALUES (:key, :payload)'),
                               [dict(key=key, payload='历史-' + key) for key in old])
        def records(table):
            return connection.execute(text(f'SELECT * FROM {table} ORDER BY workspace')).all()

        before = {table: records(table) for table in TABLES}
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.upgrade()
            assert {table: records(table) for table in TABLES} == before
            migration.downgrade()
            assert {table: records(table) for table in TABLES} == before
            migration.upgrade()
            for table in TABLES:
                allowed = PRODUCTS if table.endswith('_archives') else PRODUCTS + REPLACEMENTS
                insert = text(f"INSERT INTO {table} VALUES (:key, '新增')")
                for key in allowed:
                    connection.execute(insert, {'key': key})
                for key in ('unknown',) + tuple(key for key in REPLACEMENTS if key not in allowed):
                    with pytest.raises(IntegrityError), connection.begin_nested():
                        connection.execute(insert, {'key': key})
            expanded = {table: records(table) for table in TABLES}
            with pytest.raises(IntegrityError), connection.begin_nested():
                migration.downgrade()
            assert {table: records(table) for table in TABLES} == expanded
