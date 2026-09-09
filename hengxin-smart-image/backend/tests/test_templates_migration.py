import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from app.models import Base
from app.modules.skills.models import SkillRecord, SkillVersionRecord
from app.modules.templates.models import TemplateImageRecord, TemplateRecord, TemplateVersionRecord
from app.resource_models import FileRecord, UserRecord


def test_template_migration_is_repeatable_and_preserves_upstream():
    path = Path(__file__).parents[1] / 'migrations/versions/0004_templates.py'
    spec = importlib.util.spec_from_file_location('migration_templates', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    upstream = [UserRecord.__table__, FileRecord.__table__, SkillRecord.__table__, SkillVersionRecord.__table__]
    Base.metadata.create_all(engine, tables=upstream)
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                inspector = inspect(connection)
                for model in [TemplateRecord, TemplateVersionRecord, TemplateImageRecord]:
                    columns = inspector.get_columns(model.__tablename__)
                    assert {column['name'] for column in columns} == set(model.__table__.columns.keys())
                assert len(inspector.get_foreign_keys('template_versions')) == 4
                assert len(inspector.get_foreign_keys('template_images')) == 2
                migration.downgrade()
                assert set(inspect(connection).get_table_names()) == {table.name for table in upstream}
    finally:
        engine.dispose()
