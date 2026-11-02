"""Actual migration preserves switches, unknown installs, and later platform edits."""
import json
import runpy
import subprocess
import sys

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import bindparam, create_engine, text

from test_overseas_database import disposable_databases, migration_environment, migrate, snapshot, BACKEND


def test_seed_matches_preview_and_repeat_preserves_all_decisions(disposable_databases):
    url, domestic = disposable_databases
    before = snapshot(domestic)
    env = migration_environment(url)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'alembic.overseas.ini',
        'upgrade', 'overseas_0022'], cwd=BACKEND, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE overseas_installed_skill_availability SET enabled=false, version=9 WHERE id='amazon-new-product-aplus'"))
            connection.execute(text("INSERT INTO overseas_installed_skill_availability VALUES ('unknown-installed', true, 5, now(), now())"))
            connection.execute(text("INSERT INTO overseas_installed_skill_availability VALUES ('wayfair-new-product-image-set-main', true, 8, now(), now())"))
            original = connection.execute(text('SELECT id, enabled, version FROM overseas_installed_skill_availability ORDER BY id')).all()
        result = migrate(env)
        assert result.returncode == 0, result.stderr
        preview = json.loads((BACKEND.parent / 'frontend/preview-skill-platforms/seed.json').read_text(encoding='utf-8'))
        with engine.begin() as connection:
            rows = connection.execute(text('SELECT id, platforms FROM overseas_installed_skill_availability')).all()
            assert dict(rows) == {**{item['name']: item['platforms'] for item in preview}, 'unknown-installed': []}
            preserved = connection.execute(text('SELECT id, enabled, version FROM overseas_installed_skill_availability WHERE id IN :names ORDER BY id')
                .bindparams(bindparam('names', expanding=True)), {'names': [row[0] for row in original]}).all()
            assert preserved == original
            connection.execute(text("UPDATE overseas_installed_skill_availability SET platforms='[]', version=10 WHERE id='amazon-new-product-aplus'"))
            connection.execute(text("UPDATE overseas_installed_skill_availability SET platforms='[\"Walmart\", \"Amazon\"]', version=6 WHERE id='unknown-installed'"))
            with Operations.context(MigrationContext.configure(connection)):
                upgrade = runpy.run_path(str(BACKEND / 'migrations/overseas/versions/0023_skill_platforms.py'))['upgrade']
                upgrade()
                upgrade()
            assert connection.execute(text("SELECT enabled, version, platforms FROM overseas_installed_skill_availability WHERE id='amazon-new-product-aplus'")).one() == (False, 10, [])
            assert connection.execute(text("SELECT enabled, version, platforms FROM overseas_installed_skill_availability WHERE id='unknown-installed'")).one() == (True, 6, ['Walmart', 'Amazon'])
        assert snapshot(domestic) == before
    finally:
        engine.dispose()
