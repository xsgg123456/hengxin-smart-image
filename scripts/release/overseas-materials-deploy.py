"""Pinned 0.2.38 -> 0.2.39, additive list-visibility migration after drained backup.

Preserve history, material objects, execution inputs, domestic and identity runtime.
CLI: RELEASE build|prepare|deploy. Never replay a partially completed deployment.
"""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('materials_cutover', Path(__file__).with_name('overseas-images-deploy.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
d = c.d
d.TARGET_VERSION, d.BASE_VERSION = '0.2.39', '0.2.38'
d.TARGET_MIGRATION = 'overseas_0017'
c.BASE_RELEASE = c.BASE_FRONTEND_RELEASE = 'overseas-20261016-106d07d'
c.BASE_NATIVE = Path('/opt/hengxin-overseas-releases') / c.BASE_RELEASE / 'backend'
d.MIGRATION_RECOVERY = (' This release only adds the material-list visibility table. '
    'After MIGRATION_STARTED, keep intake closed on failure and inspect the actual schema, '
    'runtime and queues before reviewed forward recovery. Never downgrade or restore databases '
    'automatically. Preserve historical attachments, Codex inputs, Skills, domestic and identity services.')
c.REQUIRED |= {'scripts/release/overseas-materials-deploy.py',
    'backend/migrations/overseas/versions/0017_studio_material_visibility.py',
    'backend/app/overseas/studio/material_list.py', 'backend/tests/test_studio_material_list.py'}
TABLE_EXISTS = ("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                "AND table_name='overseas_studio_material_visibility'")


def check_schema(revision, table_count):
    assert d.r.sql('SELECT version_num FROM alembic_version') == d.DOMESTIC_MIGRATION
    assert d.u.sql('SELECT version_num FROM overseas_alembic_version') == revision
    assert d.u.sql(c.a.USAGE_COLUMN) == '0', 'Overseas usage column unexpectedly present'
    assert d.u.sql(TABLE_EXISTS) == table_count, 'Material visibility schema drift'


def schemas():
    check_schema('overseas_0016', '0')


def installed_schemas():
    check_schema(d.TARGET_MIGRATION, '1')


def migrate(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    overlay = work / 'overseas-migration-overlay.json'
    d.m.private(overlay, {'services': {'migrate': {'image': identity,
        'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}})
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    current = json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json', capture=True))
    assert before == current, 'Migration Compose baseline drift'
    after = json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json', overlay=overlay, capture=True))
    d.m.same_settings(before, after, ['migrate'])
    assert after['services']['migrate']['image'] == identity, 'Migration image drift'
    d.m.private(work / 'MIGRATION_STARTED', d.MIGRATION_RECOVERY)
    d.m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never',
        'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', d.TARGET_MIGRATION, overlay=overlay)
    installed_schemas()
    d.m.private(work / 'MIGRATION_VERIFIED', d.TARGET_MIGRATION + ': list visibility only')


d.schemas, d.installed_schemas, d.before_switch = schemas, installed_schemas, migrate
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
