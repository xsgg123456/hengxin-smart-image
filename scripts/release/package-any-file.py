"""Package the reviewed arbitrary-format original-attachment release."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('any_file_package_base', Path(__file__).with_name('package-skill-availability.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.RELEASE_PREFIX = '0.2.48', 'overseas-20261022-'
p.DOMESTIC_MIGRATION, p.OVERSEAS_MIGRATION = '0032', 'overseas_0020'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-any-file.py')
REQUIRED = p.REQUIRED | {'scripts/release/overseas-any-file-deploy.py',
    'backend/app/overseas/studio/files.py', 'backend/app/overseas/studio/router.py',
    'backend/tests/test_studio_any_file.py', 'backend/tests/test_overseas_upload_limits.py'}
p.REQUIRED = REQUIRED
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
