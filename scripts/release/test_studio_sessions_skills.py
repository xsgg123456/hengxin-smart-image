"""Pinned Skill verification rejects drift without changing installed content."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('defect', ['none', 'release', 'packages', 'files', 'inode',
    'writable', 'old_volume', 'root', 'empty_results', 'duplicate_name', 'result_files', 'writable_skill'])
def test_current_collection_is_exactly_verified(tmp_path, monkeypatch, defect):
    s = load('overseas-studio-sessions-skills')
    native = dict(release=s.RELEASE, packages=15, files=227, directoryIdentity=dict(device=1, inode=2))
    api = copy.deepcopy(native)
    sandbox = dict(copy.deepcopy(native), uid=999,
                   results=[dict(name=str(i), files=17 if i == 0 else 15, readOnly=True) for i in range(15)])
    mount = dict(Destination=str(s.runtime.ROOT), Source=str(s.runtime.ROOT), RW=False)
    if defect == 'release': api['release'] = s.runtime.RELEASE
    elif defect == 'packages': api['packages'] = 14
    elif defect == 'files': api['files'] = 181
    elif defect == 'inode': api['directoryIdentity']['inode'] = 3
    elif defect == 'writable': mount['RW'] = True
    elif defect == 'old_volume': mount['Source'] = s.runtime.OLD_VOLUME
    elif defect == 'root': sandbox['uid'] = 0
    elif defect == 'empty_results': sandbox['results'] = []
    elif defect == 'duplicate_name': sandbox['results'][0]['name'] = '1'
    elif defect == 'result_files': sandbox['results'][0]['files'] = 16
    elif defect == 'writable_skill': sandbox['results'][0]['readOnly'] = False
    def invoke(target, args, worker=False):
        assert worker and target == tmp_path
        assert args in (['-m', 'app.overseas.management.skill_install', 'verify'], ['-m', 'app.overseas.management.skill_probe'])
        return sandbox if args[-1].endswith('skill_probe') else native
    monkeypatch.setattr(s.runtime, 'invoke', invoke)
    saved = []
    r = SimpleNamespace(API='overseas-only', private=lambda path, value: saved.append(value),
        run=lambda *args, **kwargs: json.dumps([{'Mounts': [mount]}]) if 'inspect' in args else json.dumps(api))
    if defect == 'none':
        s.verify(r, tmp_path, tmp_path)
        assert saved[0]['modelCalls'] == 0 and saved[0]['sharedDirectory']
    else:
        with pytest.raises(AssertionError): s.verify(r, tmp_path, tmp_path)
        assert not saved


def test_new_release_only_replaces_verifier_and_packages_it():
    release = load('overseas-studio-sessions-deploy')
    package = load('package-studio-sessions')
    assert release.m.skills.verify is release.skills_check.verify
    path = 'scripts/release/overseas-studio-sessions-skills.py'
    assert path in release.REQUIRED and path in package.p.REQUIRED
    assert package.selected(path) == path
