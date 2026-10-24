"""Package reviewed reliable studio delivery, using the complete source allowlist."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('delivery_reliability_package_base',
    Path(__file__).with_name('package-studio-sessions.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.RELEASE_PREFIX = '0.2.51', 'overseas-20261024-'
p.DOMESTIC_MIGRATION, p.OVERSEAS_MIGRATION = '0032', 'overseas_0021'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-delivery-reliability.py')
ENTRY = 'scripts/release/studio-delivery-reliability-20261024.py'
HELPERS = {ENTRY, 'scripts/release/studio-delivery-release-repair.py',
           'scripts/release/studio-delivery-repair-runtime.py'}
p.REQUIRED |= {*HELPERS, 'backend/app/overseas/studio/delivery.py',
    'backend/app/overseas/studio/delivery_repair.py',
    'backend/app/overseas/studio/delivery_snapshot.py', 'backend/app/overseas/studio/delivery_recovery.py',
    'backend/tests/test_studio_delivery_bridge.py', 'backend/tests/test_studio_formal_delivery.py',
    'backend/tests/test_studio_image_recovery.py', 'backend/tests/test_studio_completion.py',
    'backend/tests/test_studio_delivery_snapshot.py', 'backend/tests/test_studio_delivery_recovery.py'}
_selected = p.selected


def selected(path):
    return path if path in HELPERS else _selected(path)


p.selected = selected
validate, build = p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
