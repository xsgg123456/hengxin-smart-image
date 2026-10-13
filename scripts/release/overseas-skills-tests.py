"""Deployment must prove one read-only catalog under both actual runtimes."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('skills_ops', Path(__file__).with_name('overseas-skills-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def test_environment_is_overseas_only_and_does_not_inherit_unrelated_secrets(tmp_path, monkeypatch):
    path = tmp_path / 'worker.env'
    path.write_text('OVERSEAS_APP_ENV=production\nOVERSEAS_LOCAL_SKILL_ROOT="' + str(s.ROOT) + '"\nOVERSEAS_MINIO_SECRET_KEY="isolated fixture"\n')
    monkeypatch.setattr(s, 'ENVIRONMENT', path)
    monkeypatch.setenv('DATABASE_URL', 'must-not-inherit-domestic')
    result = s.environment()
    assert result['HX_BUSINESS_CONTEXT'] == 'overseas' and 'DATABASE_URL' not in result
    assert result['OVERSEAS_MINIO_SECRET_KEY'] == 'isolated fixture'
    path.write_text('OVERSEAS_APP_ENV=production\nOVERSEAS_LOCAL_SKILL_ROOT=/wrong-business\n')
    with pytest.raises(AssertionError):
        s.environment()


def test_overlay_replaces_only_local_skills_with_read_only_bind():
    mount = s.overlay()
    assert mount == dict(type='bind', source=str(s.ROOT), target=str(s.ROOT), read_only=True,
                         bind={'create_host_path': False})


@pytest.mark.skipif(os.name != 'posix' or getattr(os, 'geteuid', lambda: -1)() != 0,
                   reason='real production POSIX root ownership and umask required')
@pytest.mark.parametrize('existing', [False, True])
def test_install_catalog_is_traversable_under_private_deployer_umask(tmp_path, monkeypatch, existing):
    root = tmp_path / 'catalog'
    root.mkdir()
    releases = root / 'releases'
    if existing:
        releases.mkdir(mode=0o700)
    monkeypatch.setattr(s, 'ROOT', root)
    def installed(*args):
        assert releases.stat().st_mode & 0o777 == 0o755
        # The installer can create the catalog without loosening unrelated private files.
        private = tmp_path / 'private'
        private.mkdir()
        assert private.stat().st_mode & 0o777 == 0o700
        return dict(release=s.RELEASE, packages=14, files=181)
    monkeypatch.setattr(s, 'invoke', installed)
    previous = os.umask(0o077)
    try:
        s.install(SimpleNamespace(private=lambda *args: None), tmp_path, tmp_path, tmp_path)
    finally:
        os.umask(previous)


@pytest.mark.skipif(os.name != 'posix' or getattr(os, 'geteuid', lambda: -1)() != 0,
                   reason='POSIX symlink safety')
def test_install_does_not_chmod_linked_release_directory(tmp_path, monkeypatch):
    root, outside = tmp_path / 'catalog', tmp_path / 'private'
    root.mkdir()
    outside.mkdir(mode=0o700)
    (root / 'releases').symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(s, 'ROOT', root)
    monkeypatch.setattr(s, 'invoke', lambda *args: pytest.fail('must not invoke installer'))
    with pytest.raises(AssertionError):
        s.install(SimpleNamespace(private=lambda *args: None), tmp_path, tmp_path, tmp_path)
    assert outside.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('defect', ('none', 'different_inode', 'writable', 'old_volume', 'missing_files', 'root_probe'))
def test_runtime_verification_rejects_partial_or_divergent_installations(tmp_path, monkeypatch, defect):
    evidence = dict(release=s.RELEASE, packages=14, files=181,
                    directoryIdentity=dict(device=1, inode=2))
    sandbox = dict(evidence, uid=999, results=[{'readOnly': True}])
    api = json.loads(json.dumps(evidence))
    mount = dict(Destination=str(s.ROOT), Source=str(s.ROOT), RW=False)
    if defect == 'different_inode':
        api['directoryIdentity']['inode'] = 9
    elif defect == 'writable':
        mount['RW'] = True
    elif defect == 'old_volume':
        mount['Source'] = s.OLD_VOLUME
    elif defect == 'missing_files':
        api['files'] = 180
    elif defect == 'root_probe':
        sandbox['uid'] = 0
    calls = []
    def invoke(target, arguments, worker=False):
        assert worker
        return sandbox if arguments[-1].endswith('skill_probe') else evidence
    monkeypatch.setattr(s, 'invoke', invoke)
    runtime = SimpleNamespace(API='overseas-only',
        run=lambda *args, **kwargs: json.dumps([{'Mounts': [mount]}]) if 'inspect' in args else json.dumps(api),
        private=lambda path, value: calls.append(value))
    if defect != 'none':
        with pytest.raises(AssertionError):
            s.verify(runtime, tmp_path, tmp_path)
        assert calls == []
    else:
        s.verify(runtime, tmp_path, tmp_path)
        assert calls[0]['sharedDirectory'] and calls[0]['modelCalls'] == 0
