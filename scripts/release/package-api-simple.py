"""Package the API simplification with the reviewed production privacy allowlist."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('retry_package', Path(__file__).with_name('package-api-retry.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP = p.APP
ENTRY = 'scripts/release/api-simple-deploy.py'
HANDOFF = 'scripts/release/api-simple-handoff.py'
REQUIRED = p.REQUIRED | {ENTRY, HANDOFF}
original_selected, original_validate = p.selected, p.validate


def selected(path):
    return path if path in {ENTRY, HANDOFF} else original_selected(path)


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing API simplification release files: ' + ', '.join(sorted(missing)))
    original_validate(files)


package = p.p.p
package.VERSION = '0.2.45'
package.RELEASE_PREFIX = 'domestic-api-simple-20261020-'
package.DOMESTIC_MIGRATION = '0031'
package.OVERSEAS_MIGRATION = 'overseas_0019'
package.PACKAGING_HELPERS = (*package.PACKAGING_HELPERS, 'package-api-simple.py')
package.selected, package.validate = selected, validate


def build(repo):
    return p.build(repo)


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
