"""Committed, reviewed retention release with inherited privacy/archive/install checks."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('simple_package', Path(__file__).with_name('package-api-simple.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP, package = p.APP, p.package
SCRIPTS = {'retention-management-' + name + '.py' for name in
           ('deploy', 'runtime', 'native', 'drain', 'backup', 'verify')}
REQUIRED = p.REQUIRED | {'scripts/release/' + name for name in SCRIPTS} | {
    'backend/migrations/versions/0032_retention_observability.py'}
original_selected, original_validate = p.selected, p.validate


def selected(path):
    return path if path in {'scripts/release/' + name for name in SCRIPTS} else original_selected(path)


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing retention management files: ' + ', '.join(sorted(missing)))
    if len([name for name in files if name.startswith('backend/migrations/versions/0032_')]) != 1:
        raise ValueError('Missing unique 0032 retention migration')
    original_validate(files)


package.VERSION = '0.2.46'
package.RELEASE_PREFIX = 'domestic-retention-20261021-'
package.DOMESTIC_MIGRATION = '0032'
package.OVERSEAS_MIGRATION = 'overseas_0019'
package.PACKAGING_HELPERS = (*package.PACKAGING_HELPERS, 'package-retention-management.py')
package.selected, package.validate = selected, validate


def build(repo):
    return p.build(repo)


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
