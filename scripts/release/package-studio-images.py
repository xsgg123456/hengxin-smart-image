"""Package the 0.2.38 studio images release without altering historical defaults."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('images_package', Path(__file__).with_name('package-overseas.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
p.VERSION = '0.2.38'
p.RELEASE_PREFIX = 'overseas-20261016-'
p.DOMESTIC_MIGRATION = '0029'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-images.py')
p.REQUIRED = p.REQUIRED | {
    'scripts/release/overseas-images-deploy.py',
    'backend/migrations/versions/0029_api_task_deletions.py',
    'backend/app/overseas/studio/image_edits.py',
    'backend/tests/test_studio_image_edits.py',
    'backend/tests/test_studio_image_preview.py',
}
VERSION, REQUIRED = p.VERSION, p.REQUIRED
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
