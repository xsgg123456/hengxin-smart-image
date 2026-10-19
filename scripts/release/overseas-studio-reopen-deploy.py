"""Pinned 0.2.42 -> 0.2.43 studio reopen release; no schema migration.

Reuse drained cutover, isolated backup restore, broker and domestic protections.
Never replay a failed deploy or restore production databases automatically.
"""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('studio_reopen_base', Path(__file__).with_name('overseas-archive-deletion-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d, m, u = a.d, a.m, a.u

a.BASE_VERSION = d.BASE_VERSION = '0.2.42'
d.TARGET_VERSION = '0.2.43'
a.BASE_RELEASE = 'overseas-20261019-daf9d5e'
a.BASE_IMAGE = 'sha256:572ab29546b72b7c7fbc32156550991b7806568eeaaeff5d437752fc80572950'
a.OVERSEAS_PATHS = {unit: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend' for unit in u.UNITS}
u.DROP = 'zzzzzz-studio-reopen-20261019.conf'
a.c.REQUIRED |= {'scripts/release/overseas-studio-reopen-deploy.py'}
d.MIGRATION_RECOVERY = (' No schema migration in this release. Keep intake closed on failure; '
    'inspect phase, queues and runtime before reviewed forward recovery. Never restore or downgrade '
    'production databases. Preserve domestic, identity, credential broker and conversation files.')


def schemas():
    a.check_schema('overseas_0019', '1')


def verify_unchanged_data(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    before = json.loads((destination / 'fingerprints.json').read_text())
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before, 'Data drift after backup'
    m.private(work / 'SCHEMA_UNCHANGED', 'overseas_0019 and domestic 0030; exact overseas row hashes unchanged')


# a.prepare resolves its module-level schemas function; d also calls its own hook.
a.schemas = d.schemas = d.installed_schemas = schemas
d.before_switch = verify_unchanged_data
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
