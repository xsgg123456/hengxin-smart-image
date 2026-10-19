"""Package approved studio completion/reopening; exclude preview entry points."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('studio_reopen_package_base', Path(__file__).with_name('package-archive-deletion.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
p = previous.p
p.VERSION = '0.2.43'
p.PACKAGING_HELPERS = (*p.PACKAGING_HELPERS, 'package-studio-reopen.py')
p.REQUIRED = previous.REQUIRED | {'scripts/release/overseas-studio-reopen-deploy.py'}
selected, validate, build = p.selected, p.validate, p.build

if __name__ == '__main__':
    print(json.dumps(build(Path(__file__).resolve().parents[2])))
