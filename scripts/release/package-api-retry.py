"""Reuse reviewed package/privacy rules for the additive domestic 0031 release."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('retirement_package', Path(__file__).with_name('package-retirement.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
APP = p.APP
SCRIPTS = {'api-retry-deploy.py', 'domestic-deploy.py', 'domestic-runtime.py'}
REQUIRED = p.REQUIRED | {'scripts/release/' + name for name in SCRIPTS} | {
    'backend/migrations/versions/0031_api_retry_policy.py',
    'backend/app/modules/api_image_edits/retry_policy.py',
    'backend/app/modules/api_image_edits/limiter.py'}
original_selected = p.selected


def selected(path):
    if path in {'scripts/release/' + name for name in SCRIPTS}:
        return path
    return original_selected(path)


original_validate = p.validate


def validate(files):
    if missing := REQUIRED - files.keys():
        raise ValueError('Missing API retry release files: ' + ', '.join(sorted(missing)))
    original_validate(files)


p.p.VERSION = '0.2.44'
p.p.RELEASE_PREFIX = 'domestic-api-retry-20261020-'
p.p.DOMESTIC_MIGRATION = '0031'
p.p.OVERSEAS_MIGRATION = 'overseas_0019'
p.p.PACKAGING_HELPERS = (*p.p.PACKAGING_HELPERS, 'package-api-retry.py')
p.p.selected, p.p.validate = selected, validate


def build(repo):
    return p.build(repo)


if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
