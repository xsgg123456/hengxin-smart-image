"""Migration seeds exactly two switches and never resets a subsequent owner decision."""
import runpy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_seed_and_repeat_preserve_decision_and_domestic(disposable_databases):
    url, domestic = disposable_databases
    before = snapshot(domestic)
    result = migrate(migration_environment(url))
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            rows = connection.execute(text('SELECT id, enabled, version FROM overseas_installed_skill_availability')).all()
            assert set(rows) == {('amazon-new-product-image-set', True, 1), ('amazon-new-product-aplus', True, 1)}
            connection.execute(text("UPDATE overseas_installed_skill_availability SET enabled=false, version=2 WHERE id='amazon-new-product-aplus'"))
            with Operations.context(MigrationContext.configure(connection)):
                upgrade = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0020_skill_availability.py'))['upgrade']
                upgrade()
                upgrade()
            rows = connection.execute(text('SELECT id, enabled, version FROM overseas_installed_skill_availability')).all()
            assert set(rows) == {('amazon-new-product-image-set', True, 1), ('amazon-new-product-aplus', False, 2)}
        assert snapshot(domestic) == before
    finally:
        engine.dispose()
