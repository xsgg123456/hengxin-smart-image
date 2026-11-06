"""Offline bundles remain portable; installed releases contain only indexes."""
import json
import shutil
from pathlib import Path

import pytest

from app.overseas.management import installed_catalog as catalog, skill_install


@pytest.fixture
def installation(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    root.mkdir()
    monkeypatch.setattr(skill_install, 'root_config', lambda: (root, False))
    return root


def make_bundle(tmp_path, contents):
    source = tmp_path / 'source'
    source.mkdir(parents=True)
    rows = []
    for name, content in contents.items():
        package = source / name
        package.mkdir()
        (package / 'SKILL.md').write_text(
            f'---\nname: {name}\ndescription: Complete package\n---\n{content}', encoding='utf-8')
        (package / 'empty').mkdir()
        (package / 'data.bin').write_bytes(bytes(range(256)))
        rows.append(dict(name=name, source=name, displayName=name))
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps(rows), encoding='utf-8')
    return Path(skill_install.bundle(source, mapping, tmp_path / 'bundles')['path'])


def test_offline_bundle_portable_install_reuses_unchanged_objects(installation, tmp_path):
    bundle = make_bundle(tmp_path / 'first', {'alpha': 'first', 'beta': 'first'})
    portable = skill_install.verify_bundle(bundle)
    assert portable['schema'] == 1
    assert {path.name for path in bundle.iterdir()} == {'manifest.json', 'alpha', 'beta'}
    first = skill_install.install(bundle)
    directory, manifest = catalog.release_manifest(installation, first['release'])
    assert manifest['schema'] == 2 and manifest['items'] == portable['items']
    beta = catalog.package_directory(directory, manifest['items'][1])
    unchanged = {str(path.relative_to(beta)): (path.stat().st_ino, path.stat().st_mtime_ns)
                 for path in [beta, *beta.rglob('*')]}
    assert skill_install.install(bundle) == first
    changed = make_bundle(tmp_path / 'second', {'alpha': 'second', 'beta': 'first'})
    second = skill_install.install(changed)
    assert second['release'] != first['release']
    assert unchanged == {str(path.relative_to(beta)): (path.stat().st_ino, path.stat().st_mtime_ns)
                         for path in [beta, *beta.rglob('*')]}
    assert len(list((installation / 'packages').glob('*/*'))) == 3
    for release in (installation / 'releases').iterdir():
        assert {path.name for path in release.iterdir()} == {'manifest.json'}
    assert (beta / 'empty').is_dir()
    assert (beta / 'data.bin').read_bytes() == bytes(range(256))
    assert skill_install.verify_bundle(bundle) == portable


def test_offline_replace_keeps_legacy_and_omitted_history_without_gc(installation, tmp_path):
    bundle = make_bundle(tmp_path / 'legacy', {'alpha': 'old', 'beta': 'old'})
    legacy = installation / 'releases' / bundle.name
    legacy.parent.mkdir()
    shutil.copytree(bundle, legacy)
    (installation / 'current.json').write_text(json.dumps({'release': bundle.name}), encoding='utf-8')
    old_manifest = (legacy / 'manifest.json').read_bytes()
    first = skill_install.install(bundle)
    directory, manifest = catalog.release_manifest(installation, first['release'])
    old_objects = [catalog.package_directory(directory, item) for item in manifest['items']]
    replacement = make_bundle(tmp_path / 'replacement', {'alpha': 'new'})
    skill_install.install(replacement)
    assert [item['name'] for item in catalog.read_catalog(installation)[1]] == ['alpha']
    assert (legacy / 'manifest.json').read_bytes() == old_manifest
    assert (legacy / 'alpha/SKILL.md').read_bytes().endswith(b'old')
    assert (legacy / 'beta/SKILL.md').read_bytes().endswith(b'old')
    assert all((path / 'SKILL.md').read_bytes().endswith(b'old') for path in old_objects)
    assert len(list((installation / 'packages').glob('*/*'))) == 3


def test_offline_copy_failure_preserves_pointer_and_cleans_staging(installation, tmp_path, monkeypatch):
    first = make_bundle(tmp_path / 'first', {'alpha': 'first'})
    skill_install.install(first)
    pointer = (installation / 'current.json').read_bytes()
    second = make_bundle(tmp_path / 'second', {'alpha': 'second'})
    original = catalog.verify_package
    def fail(directory, *args, **kwargs):
        if directory.name.startswith('.install-'):
            raise ValueError('injected copy validation failure')
        return original(directory, *args, **kwargs)
    monkeypatch.setattr(catalog, 'verify_package', fail)
    with pytest.raises(ValueError, match='copy validation'):
        skill_install.install(second)
    assert (installation / 'current.json').read_bytes() == pointer
    assert not list(installation.rglob('.install-*'))
    release, items = catalog.read_catalog(installation)
    directory, _ = catalog.release_manifest(installation, release)
    assert catalog.verify_package(directory, items[0]).files['SKILL.md'].endswith(b'first')
