"""Package the approved 0.2.39 material list and archive browser release."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('materials_package', Path(__file__).with_name('package-studio-images.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION = '0.2.39'
p.OVERSEAS_MIGRATION = 'overseas_0017'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-materials-archive.py')
p.REQUIRED |= {
    'scripts/release/overseas-materials-deploy.py',
    'backend/migrations/overseas/versions/0017_studio_material_visibility.py',
    'backend/app/overseas/studio/material_list.py',
    'backend/tests/test_studio_material_list.py',
}
VERSION, REQUIRED = p.VERSION, p.REQUIRED
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
