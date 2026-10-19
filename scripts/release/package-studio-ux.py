"""Package the approved 0.2.41 studio UX and archive audit release."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('studio_ux_package_base', Path(__file__).with_name('package-retirement.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION = '0.2.41'
p.RELEASE_PREFIX = 'overseas-20261019-'
p.DOMESTIC_MIGRATION, p.OVERSEAS_MIGRATION = '0030', 'overseas_0018'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-ux.py')
REQUIRED = previous.REQUIRED | {
    'scripts/release/overseas-studio-ux-deploy.py',
    'scripts/release/overseas-materials-deploy.py',
    'scripts/release/overseas-images-deploy.py',
    'scripts/release/member-release-backup.py',
    'backend/migrations/overseas/versions/0017_studio_material_visibility.py',
    'backend/migrations/overseas/versions/0018_archive_events.py',
    'backend/app/overseas/archives/audit.py',
    'backend/tests/test_overseas_archive_audit.py',
    'backend/tests/test_overseas_archive_audit_migration.py',
    'backend/app/overseas/studio/material_list.py',
}
previous.REQUIRED = p.REQUIRED = REQUIRED
VERSION = p.VERSION
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
