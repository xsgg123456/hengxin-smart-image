"""Reviewed 0.2.49 package; no migration, preview assets or private runtime data."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('retention_package', Path(__file__).with_name('package-retention-management.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP, package = p.APP, p.package
SCRIPTS = {'domestic-record-filters-' + name + '.py' for name in ('deploy', 'runtime', 'verify', 'native', 'schema')}
REQUIRED = p.REQUIRED | {'scripts/release/' + name for name in SCRIPTS} | {
    'backend/app/modules/api_image_edits/listing.py',
    'backend/tests/test_api_image_records.py', 'backend/tests/test_api_image_records_pg.py',
    'backend/app/execution/cleanup_paths.py', 'backend/app/execution/cleanup_diagnostics.py',
    'backend/tests/test_cleanup_paths.py', 'backend/tests/test_cleanup_diagnostics.py',
    'backend/tests/test_cleanup_retention_safety.py', 'backend/tests/test_cleanup_retry_pg.py',
    'backend/tests/test_cleanup_mounts.py',
}
original_selected, original_validate = p.selected, p.validate


def selected(path):
    return path if path in {'scripts/release/' + name for name in SCRIPTS} else original_selected(path)


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing record filters files: ' + ', '.join(sorted(missing)))
    if any('preview-records-scope' in name for name in files):
        raise ValueError('Independent preview must not be packaged')
    original_validate(files)


package.VERSION = '0.2.49'
package.RELEASE_PREFIX = 'domestic-record-filters-20261022-'
package.DOMESTIC_MIGRATION = '0032'
package.OVERSEAS_MIGRATION = 'overseas_0020'
package.PACKAGING_HELPERS = (*package.PACKAGING_HELPERS, 'package-record-filters.py')
package.selected, package.validate = selected, validate


def build(repo):
    return p.build(repo)


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
