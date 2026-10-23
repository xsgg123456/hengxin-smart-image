"""Verify the read-only production Skill collection observed on 2026-10-24."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('sessions_skill_runtime', Path(__file__).with_name('overseas-skills-runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
RELEASE = '8ea5d6ffc55e6508a1f4003a8f5bed4ffc3ca4b25de42cba29f8724a8488c339'
PACKAGES, FILES = 15, 227


def verify(r, work, target):
    native = runtime.invoke(target, ['-m', 'app.overseas.management.skill_install', 'verify'], worker=True)
    sandbox = runtime.invoke(target, ['-m', 'app.overseas.management.skill_probe'], worker=True)
    api = json.loads(r.run('docker', 'exec', r.API, 'python', '-m',
        'app.overseas.management.skill_install', 'verify', capture=True))
    live = json.loads(r.run('docker', 'inspect', r.API, capture=True))[0]
    mount = [item for item in live['Mounts'] if item['Destination'] == str(runtime.ROOT)]
    assert len(mount) == 1 and mount[0]['Source'] == str(runtime.ROOT) and mount[0]['RW'] is False
    for result in (native, sandbox, api):
        assert result['release'] == RELEASE and result['packages'] == PACKAGES and result['files'] == FILES, 'Production Skill collection drift'
    assert native['directoryIdentity'] == api['directoryIdentity'] == sandbox['directoryIdentity']
    assert sandbox['uid'] != 0 and len(sandbox['results']) == PACKAGES
    assert len({row['name'] for row in sandbox['results']}) == PACKAGES
    assert sum(row['files'] for row in sandbox['results']) == FILES
    assert all(row['readOnly'] for row in sandbox['results'])
    r.private(work / 'SKILLS_VERIFIED.json', dict(native=native, api=api, sandbox=sandbox,
                                               modelCalls=0, sharedDirectory=True))
