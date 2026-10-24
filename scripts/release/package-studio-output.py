"""Package only committed, approved sources; private incident evidence stays out."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('studio_output_package_base',
    Path(__file__).with_name('package-studio-delivery-reliability.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.OVERSEAS_MIGRATION = '0.2.52', 'overseas_0022'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-output.py')
ENTRY = 'scripts/release/studio-output-deploy.py'
HELPERS = {ENTRY, 'scripts/release/studio-output-data.py',
           'scripts/release/studio-output-settle.py', 'scripts/release/studio-output-settle-runtime.py'}
p.REQUIRED |= HELPERS | {
    'backend/migrations/overseas/versions/0022_studio_output_files.py',
    'backend/app/overseas/studio/output_store.py',
    'backend/app/overseas/studio/recovery_files.py',
    'backend/app/overseas/studio/recovery_listing.py',
    'backend/app/overseas/studio/recovery_router.py',
    'backend/app/overseas/studio/recovery_transport.py',
    'backend/app/overseas/studio/output_files.py',
    'backend/tests/test_studio_open_outputs.py',
    'backend/tests/test_studio_output_lifecycle.py',
    'backend/tests/test_studio_recovery_transport.py',
    'backend/tests/test_studio_recovery_versions.py',
    'backend/tests/test_overseas_studio_file_recovery.py'}
_selected = p.selected


def selected(path):
    return path if path in HELPERS else _selected(path)


p.selected = selected
validate, build = p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
