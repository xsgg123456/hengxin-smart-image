"""Package the reviewed archive deletion release with the authentication fix."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('archive_deletion_package', Path(__file__).with_name('package-studio-ux.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.OVERSEAS_MIGRATION = '0.2.42', 'overseas_0019'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-archive-deletion.py')
REQUIRED = previous.REQUIRED | {
    'scripts/release/overseas-archive-deletion-deploy.py',
    'backend/migrations/overseas/versions/0019_archive_deletion.py',
    'backend/app/overseas/archives/deletion.py', 'backend/app/overseas/archives/cleanup.py',
    'backend/tests/test_overseas_archive_deletion.py',
    'backend/tests/test_overseas_archive_deletion_migration.py',
    'backend/tests/test_overseas_archive_deletion_postgres.py',
    'backend/app/execution/credential_broker_client.py',
    'backend/app/execution/managed_credentials.py',
}
p.REQUIRED = REQUIRED
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
