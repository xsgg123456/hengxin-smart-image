"""Package committed, independently reviewed multi-session production sources."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('sessions_package_base', Path(__file__).with_name('package-any-file.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.RELEASE_PREFIX = '0.2.50', 'overseas-20261024-'
p.DOMESTIC_MIGRATION, p.OVERSEAS_MIGRATION = '0032', 'overseas_0021'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-sessions.py')
p.REQUIRED |= {
    'scripts/release/overseas-studio-sessions-deploy.py',
    'scripts/release/overseas-studio-sessions-data.py',
    'scripts/release/overseas-studio-sessions-skills.py',
    'backend/migrations/overseas/versions/0021_studio_sessions.py',
    'backend/tests/test_studio_sessions.py',
    'backend/tests/studio_sessions_helpers.py',
    'backend/tests/test_studio_sessions_migration.py',
    'backend/tests/test_overseas_studio_conversations.py',
    'backend/app/overseas/studio/image_recovery.py',
    'backend/app/overseas/studio/delivery.py',
    'backend/app/overseas/permissions.py',
}
_validate = p.validate


def validate(files):
    _validate(files)
    if any(name.startswith('frontend/dist/') and name.endswith('.html') and
           'preview' in name for name in files):
        raise ValueError('Preview entry point in production package')


p.validate = validate
selected, build = p.selected, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
