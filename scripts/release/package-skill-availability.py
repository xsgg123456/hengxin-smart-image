"""Package the approved composer, batch material removal and Skill switch release."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('skill_availability_package_base', Path(__file__).with_name('package-studio-reopen.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION, p.RELEASE_PREFIX = '0.2.47', 'overseas-20261022-'
p.DOMESTIC_MIGRATION, p.OVERSEAS_MIGRATION = '0032', 'overseas_0020'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-skill-availability.py')
REQUIRED = p.REQUIRED | {'scripts/release/overseas-skill-availability-deploy.py',
    'scripts/release/overseas-skill-availability-owner.py',
    'backend/migrations/overseas/versions/0020_skill_availability.py',
    'backend/tests/test_overseas_skill_availability.py',
    'backend/tests/test_overseas_skill_owner_configuration.py',
    'backend/tests/test_overseas_skill_availability_migration.py',
    'backend/tests/test_overseas_skill_availability_postgres.py'}
p.REQUIRED = REQUIRED
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
