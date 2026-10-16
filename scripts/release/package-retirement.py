"""Package only reviewed committed source, with privacy-audited production assets."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('overseas_package', Path(__file__).with_name('package-overseas.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP = p.APP
SCRIPTS = {'retirement-' + name + '.py' for name in ('deploy', 'runtime', 'native', 'drain', 'backup', 'verify')}
SCRIPTS |= {'domestic-gate.py', 'domestic-drain.py', 'domestic-backup.py'}
EXACT = {'infra/hengxin-domestic-deletions.service'}
RETIRED_REQUIRED = {'backend/tests/fixtures/cli_revision_briefs.json'}
REQUIRED = (p.REQUIRED - RETIRED_REQUIRED) | EXACT | {'scripts/release/' + name for name in SCRIPTS} | {
    'backend/migrations/versions/0030_retire_legacy.py',
    'backend/migrations/versions/0029_api_task_deletions.py',
    'backend/app/retention/worker.py'}
FORBIDDEN = ('backend/app/modules/tasks/', 'backend/app/modules/templates/',
             'backend/app/modules/products/', 'backend/app/modules/skills/',
             'backend/app/modules/archives/', 'backend/app/modules/revisions/',
             'backend/app/retention/legacy.py')
original_selected = p.selected


def selected(path):
    if path in {'scripts/release/' + name for name in SCRIPTS}:
        return path
    if path in {APP + name for name in EXACT}:
        return path.removeprefix(APP)
    return original_selected(path)


def validate(files):
    if any(name.startswith(FORBIDDEN) for name in files):
        raise ValueError('Retired business source remains in package')
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing retirement runtime files: ' + ', '.join(sorted(missing)))
    original_validate(files)


original_validate = p.validate
p.VERSION = '0.2.40'
p.RELEASE_PREFIX = 'domestic-retire-20261016-'
p.DOMESTIC_MIGRATION = '0030'
p.OVERSEAS_MIGRATION = 'overseas_0017'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-retirement.py')
p.REQUIRED = REQUIRED
p.selected, p.validate = selected, validate


def build(repo):
    return p.build(repo)


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
