"""Real PostgreSQL migration preserves historical identities and enforces ownership."""
import importlib
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from test_domestic_studio_bindings_pg import database

migration = importlib.import_module('migrations.versions.0044_domestic_tasks')


def test_0044_preserves_all_history_and_constrains_owner_workspace(database):
    schema = database.get_execution_options()['schema_translate_map'][None]
    owner, other, first, second, deleted = [uuid4() for _ in range(5)]
    with database.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(text('CREATE TABLE users (id uuid PRIMARY KEY)'))
        connection.execute(text('INSERT INTO users VALUES (:owner), (:other)'), dict(owner=owner, other=other))
        connection.execute(text('CREATE TABLE domestic_studio_conversations '
            '(id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users, workspace varchar(20) NOT NULL, '
            'name varchar(30) NOT NULL, version integer NOT NULL, session_id varchar(128), '
            'created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL)'))
        for identity, name in ((first, '历史甲'), (second, '历史乙')):
            connection.execute(text('INSERT INTO domestic_studio_conversations VALUES '
                "(:id,:owner,'camera',:name,7,:thread,'2026-11-01T00:00:00Z','2026-11-02T00:00:00Z')"),
                dict(id=identity, owner=owner, name=name, thread='native-' + str(identity)))
        connection.execute(text('CREATE TABLE domestic_studio_conversation_deletions '
            '(conversation_id uuid PRIMARY KEY, owner_id uuid, workspace varchar(20), status varchar(20), manifest json)'))
        connection.execute(text("INSERT INTO domestic_studio_conversation_deletions VALUES "
            "(:first,:owner,'camera','delete_failed','{\"objects\":[]}'::json), "
            "(:deleted,:owner,'phone','deleted','{}'::json)"), dict(first=first, deleted=deleted, owner=owner))
        connection.execute(text('CREATE TABLE history_payload (id uuid PRIMARY KEY, conversation_id uuid, payload json)'))
        connection.execute(text("INSERT INTO history_payload VALUES (:id,:first,'{\"thread\":\"native\",\"files\":[\"unchanged\"],\"receipt\":\"same\"}'::json)"), dict(id=uuid4(), first=first))
        before = list(connection.execute(text('SELECT * FROM domestic_studio_conversations ORDER BY id')).mappings())
        payload = list(connection.execute(text('SELECT * FROM history_payload')).mappings())
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            migration.upgrade()
        rows = list(connection.execute(text('SELECT * FROM domestic_studio_conversations ORDER BY id')).mappings())
        assert [{k: v for k, v in row.items() if k != 'task_id'} for row in rows] == before
        assert rows[0]['task_id'] == rows[1]['task_id']
        assert list(connection.execute(text('SELECT * FROM history_payload')).mappings()) == payload
        task = connection.execute(text('SELECT * FROM domestic_studio_tasks')).mappings().one()
        assert task['name'] == '历史任务 · 相机配件生成' and task['owner_id'] == owner
        assert task['created_at'] == before[0]['created_at']
        assert connection.scalar(text('SELECT task_id FROM domestic_studio_conversation_deletions WHERE conversation_id=:id'), {'id': deleted}) is None
        for column, value in (('owner_id', other), ('workspace', 'case')):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text(f'UPDATE domestic_studio_conversations SET {column}=:value WHERE id=:id'),
                                   dict(value=value, id=first))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(connection))):
            with pytest.raises(RuntimeError, match='verification'):
                migration.upgrade()
        assert connection.scalar(text('SELECT count(*) FROM domestic_studio_tasks')) == 1
        fk = next(row for row in inspect(connection).get_foreign_keys('domestic_studio_conversations')
                  if row['name'] == 'fk_domestic_conversation_task_owner_workspace')
        assert fk['constrained_columns'] == ['task_id', 'owner_id', 'workspace']
