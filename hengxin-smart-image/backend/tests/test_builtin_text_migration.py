"""Exercise upgrade against an old table with a real FK and retained snapshots."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.mark.parametrize('dialect', ['sqlite', 'postgresql'])
def test_upgrade_preserves_old_skill_tasks_and_accepts_builtin(dialect):
    url = 'sqlite://' if dialect == 'sqlite' else os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL TEST_DATABASE_URL')
    engine = create_engine(url)
    schema = 'text_migration_' + uuid4().hex
    spec = importlib.util.spec_from_file_location('builtin_migration',
        Path(__file__).parents[1] / 'migrations/versions/0020_builtin_text_tasks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as c:
            if dialect == 'postgresql':
                c.execute(text(f'CREATE SCHEMA {schema}'))
                c.execute(text(f'SET LOCAL search_path TO {schema}'))
            c.execute(text('CREATE TABLE skill_versions (id integer primary key)'))
            c.execute(text('CREATE TABLE task_records (id integer primary key, '
                'skill_version_id integer NOT NULL REFERENCES skill_versions(id), skill_snapshot JSON NOT NULL)'))
            c.execute(text('INSERT INTO skill_versions VALUES (1)'))
            c.execute(text('INSERT INTO task_records VALUES (1, 1, :snapshot)'), {'snapshot': '{"version":"old"}'})
            with Operations.context(MigrationContext.configure(c)):
                module.upgrade()
                module.upgrade()
                assert c.execute(text('SELECT skill_version_id,builtin_prompt FROM task_records')).one() == (1, None)
                assert inspect(c).get_foreign_keys('task_records')[0]['referred_table'] == 'skill_versions'
                c.execute(text('INSERT INTO task_records VALUES (2,NULL,:snapshot,:prompt)'),
                    {'snapshot': '{}', 'prompt': '{"version":"text-edit-v1"}'})
                module.downgrade()
                assert c.execute(text('SELECT count(*) FROM task_records')).scalar() == 2
            if dialect == 'postgresql':
                with pytest.raises(IntegrityError), c.begin_nested():
                    c.execute(text('INSERT INTO task_records (id,skill_version_id,skill_snapshot) VALUES (3,99,:s)'), {'s': '{}'})
    finally:
        if dialect == 'postgresql':
            with engine.begin() as c:
                c.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        engine.dispose()
