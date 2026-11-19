"""Workspace migrations preserve historical rows and enforce each table's allowed values."""
import importlib
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from test_domestic_studio_bindings_pg import database

PRODUCTS_0044 = ('camera', 'case')
REPLACEMENTS_0044 = ('product', 'scene', 'phone')
PRODUCTS_0045 = PRODUCTS_0044 + ('film', 'cable', 'earbud', 'accessory')
REPLACEMENTS_0045 = REPLACEMENTS_0044 + ('edit',)
TABLES = ('domestic_studio_tasks', 'domestic_studio_conversations', 'domestic_studio_archives',
          'domestic_studio_workspaces', 'domestic_studio_skill_bindings')


@pytest.mark.parametrize('revision,old_products,old_replacements,products,replacements', [
    ('0045_domestic_workspaces', PRODUCTS_0044, REPLACEMENTS_0044, PRODUCTS_0045, REPLACEMENTS_0045),
    ('0046_general_workspace', PRODUCTS_0045, REPLACEMENTS_0045, PRODUCTS_0045 + ('general',), REPLACEMENTS_0045),
])
def test_workspace_checks_expand_without_rewriting_rows_and_refuse_lossy_downgrade(
        database, revision, old_products, old_replacements, products, replacements):
    migration = importlib.import_module('migrations.versions.' + revision)
    schema = database.get_execution_options()['schema_translate_map'][None]
    with database.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        # Use the original anonymous inline CHECK shape so PostgreSQL names each constraint.
        connection.execute(text('DROP TABLE domestic_studio_skill_bindings'))
        for table in TABLES:
            old = old_products if table.endswith('_archives') else old_products + old_replacements
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
                allowed = products if table.endswith('_archives') else products + replacements
                insert = text(f"INSERT INTO {table} VALUES (:key, '新增')")
                for key in allowed:
                    connection.execute(insert, {'key': key})
                for key in ('unknown',) + tuple(key for key in replacements if key not in allowed):
                    with pytest.raises(IntegrityError), connection.begin_nested():
                        connection.execute(insert, {'key': key})
            expanded = {table: records(table) for table in TABLES}
            with pytest.raises(IntegrityError), connection.begin_nested():
                migration.downgrade()
            assert {table: records(table) for table in TABLES} == expanded
