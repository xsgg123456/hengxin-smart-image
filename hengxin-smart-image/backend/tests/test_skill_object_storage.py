"""Object reuse and immutable metadata against actual isolated filesystem trees."""
import json
import os
import shutil

import pytest
from fastapi import HTTPException

from app.overseas.management import installed_catalog as catalog, skill_downloads
from app.overseas.management.installed_tree import digest, tree
from app.overseas.management.skill_objects import prepare_release
from app.overseas.management.skill_transfer_store import atomic_json


def source(tmp_path, name, content='first'):
    path = tmp_path / (name + '-' + content)
    path.mkdir()
    (path / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: Complete package\n---\n{content}', encoding='utf-8')
    (path / 'empty').mkdir()
    (path / 'assets').mkdir()
    (path / 'assets/data.bin').write_bytes(bytes(range(256)))
    package, entries = tree(path)
    return path, dict(name=name, displayName=name, description=package.description,
                      checksum=package.checksum, entries=entries)


def publish(root, items, sources=None):
    release = prepare_release(root, items, sources)
    atomic_json(root / 'current.json', {'release': release})
    return release


def legacy(root, items, sources):
    manifest = dict(schema=1, items=items)
    release = digest(manifest)
    folder = root / 'releases' / release
    folder.mkdir(parents=True)
    for item in items:
        shutil.copytree(sources[item['name']], folder / item['name'])
    atomic_json(folder / 'manifest.json', manifest)
    atomic_json(root / 'current.json', {'release': release})
    return release


def test_objects_reused_and_only_changed_skill_copied(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    a_source, a = source(tmp_path, 'alpha')
    b_source, b = source(tmp_path, 'beta')
    first = publish(root, [a, b], {'alpha': a_source, 'beta': b_source})
    b_path = root / 'packages/beta' / b['checksum']
    before = {str(path.relative_to(b_path)): (path.stat().st_ino, path.stat().st_mtime_ns)
              for path in [b_path, *b_path.rglob('*')]}
    new_source, updated = source(tmp_path, 'alpha', 'second')
    second = publish(root, [updated, b], {'alpha': new_source})
    assert second != first
    assert before == {str(path.relative_to(b_path)): (path.stat().st_ino, path.stat().st_mtime_ns)
                      for path in [b_path, *b_path.rglob('*')]}
    assert publish(root, [updated, b], {'alpha': new_source}) == second
    assert len(list((root / 'packages').glob('*/*'))) == 3
    assert catalog.read_catalog(root)[1] == [updated, b]
    for folder in (root / 'releases').iterdir():
        assert {path.name for path in folder.iterdir()} == {'manifest.json'}
        assert json.loads((folder / 'manifest.json').read_text())['schema'] == 2
    assert (b_path / 'empty').is_dir()
    assert (b_path / 'assets/data.bin').read_bytes() == bytes(range(256))


def test_prepare_does_not_switch_pointer_and_failure_leaves_empty_catalog(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    original = catalog.verify_package
    def fail(directory, *args, **kwargs):
        if directory.name.startswith('.install-'):
            raise ValueError('injected copy failure')
        return original(directory, *args, **kwargs)
    monkeypatch.setattr(catalog, 'verify_package', fail)
    with pytest.raises(ValueError, match='injected'):
        prepare_release(root, [item], {'alpha': path})
    empty_release, items = catalog.read_catalog(root)
    assert empty_release and items == []
    monkeypatch.setattr(catalog, 'verify_package', original)
    release = prepare_release(root, [item], {'alpha': path})
    assert release != empty_release
    assert catalog.read_catalog(root) == (empty_release, [])
    atomic_json(root / 'current.json', {'release': release})
    assert catalog.read_catalog(root)[1] == [item]
    empty = publish(root, [])
    assert catalog.read_catalog(root) == (empty, [])


def test_legacy_metadata_survives_object_migration_and_reclamation(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    old = legacy(root, [item], {'alpha': path})
    old_folder = root / 'releases' / old
    original_bytes = (old_folder / 'manifest.json').read_bytes()
    assert catalog.read_catalog(root) == (old, [item])
    new = publish(root, [item])
    assert new != old
    shutil.rmtree(old_folder / 'alpha')
    assert (old_folder / 'manifest.json').read_bytes() == original_bytes
    monkeypatch.setattr(catalog, 'root_config', lambda: (root, False))
    skill = dict(name='alpha', installedRelease=old, checksum=item['checksum'])
    assert catalog.frozen_package(skill).files['assets/data.bin'] == bytes(range(256))
    publish(root, [])
    shutil.rmtree(root / 'packages/alpha' / item['checksum'])
    assert catalog.frozen_item(skill) == (old_folder, item, False)
    with pytest.raises(FileNotFoundError):
        catalog.frozen_package(skill)
    with pytest.raises(HTTPException) as caught:
        skill_downloads.file(catalog.identity('alpha'), old, 'SKILL.md')
    assert caught.value.status_code == 410
    assert catalog.read_catalog(root)[1] == []


def test_current_missing_object_fails_catalog_and_frozen_metadata_is_available(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    release = publish(root, [item], {'alpha': path})
    monkeypatch.setattr(catalog, 'root_config', lambda: (root, False))
    skill = catalog.freeze(catalog.identity('alpha'))
    shutil.rmtree(root / 'packages/alpha' / item['checksum'])
    assert catalog.frozen_item(skill)[1] == item
    with pytest.raises(HTTPException) as caught:
        catalog.catalog()
    assert caught.value.status_code == 503
    assert catalog.release_manifest(root, release)[1]['schema'] == 2


def test_cached_object_reads_detect_same_size_in_place_tampering(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    release = publish(root, [item], {'alpha': path})
    original, calls = catalog.verify_package, []
    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(catalog, 'verify_package', counted)
    catalog.read_catalog(root)
    calls.clear()
    catalog.read_catalog(root)
    assert calls == []
    target = root / 'packages/alpha' / item['checksum'] / 'SKILL.md'
    target.write_bytes(target.read_bytes().replace(b'first', b'other'))
    with pytest.raises(ValueError, match='integrity'):
        catalog.read_catalog(root)
    monkeypatch.setattr(catalog, 'root_config', lambda: (root, False))
    with pytest.raises(HTTPException) as caught:
        skill_downloads.file(catalog.identity('alpha'), release, 'SKILL.md')
    assert caught.value.status_code == 503


@pytest.mark.parametrize('field,value', [('name', '../escape'), ('checksum', '../escape')])
def test_object_identifiers_cannot_escape_installation(tmp_path, field, value):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    item[field] = value
    with pytest.raises(ValueError):
        prepare_release(root, [item], {'alpha': path})
    assert catalog.read_catalog(root)[1] == []


def test_unsafe_manifest_entry_and_hardlinked_source_rejected(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    invalid = {**item, 'entries': {**item['entries'], '../escape': {'size': 1, 'sha256': 'a' * 64}}}
    invalid['checksum'] = digest(invalid['entries'])
    with pytest.raises(ValueError):
        prepare_release(root, [invalid], {'alpha': path})
    os.link(path / 'SKILL.md', path / 'linked.md')
    with pytest.raises(ValueError, match='unsafe'):
        prepare_release(root, [item], {'alpha': path})
    assert catalog.read_catalog(root)[1] == []


def test_schema_two_cannot_fall_back_to_local_release_tree(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    release = publish(root, [item], {'alpha': path})
    folder = root / 'releases' / release
    shutil.copytree(path, folder / 'alpha')
    with pytest.raises(ValueError, match='unexpected'):
        catalog.read_catalog(root)


def test_legacy_corruption_never_falls_back_to_healthy_shared_object(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    old = legacy(root, [item], {'alpha': path})
    publish(root, [item])
    directory = root / 'releases' / old
    (directory / 'alpha/SKILL.md').write_bytes(b'broken')
    with pytest.raises(ValueError):
        catalog.verify_package(directory, item)


@pytest.mark.skipif(os.name != 'posix', reason='Linux ownership and symlink safety')
def test_object_links_and_worker_write_permissions_are_rejected(tmp_path):
    root = tmp_path / 'installed'
    root.mkdir()
    path, item = source(tmp_path, 'alpha')
    release = publish(root, [item], {'alpha': path})
    directory = root / 'releases' / release
    target = root / 'packages/alpha' / item['checksum']
    shutil.rmtree(target)
    target.symlink_to(path, target_is_directory=True)
    with pytest.raises(ValueError, match='links'):
        catalog.verify_package(directory, item)
    target.unlink()
    shutil.copytree(path, target)
    (target / 'SKILL.md').chmod(0o666)
    with pytest.raises(ValueError, match='root-owned'):
        catalog.verify_package(directory, item, protected=True)


@pytest.mark.skipif(os.name != 'posix', reason='Published Linux ownership and permissions')
def test_protected_object_publication_and_permission_tamper(tmp_path):
    if os.geteuid() != 0:
        pytest.skip('Protected publication requires root')
    root = tmp_path / 'installed'
    root.mkdir(mode=0o755)
    path, item = source(tmp_path, 'alpha')
    release = prepare_release(root, [item], {'alpha': path}, protected=True)
    atomic_json(root / 'current.json', {'release': release})
    assert catalog.read_catalog(root, protected=True)[1] == [item]
    target = root / 'packages/alpha' / item['checksum']
    assert all(entry.stat().st_uid == 0 and not entry.stat().st_mode & 0o022
               for entry in [target, *target.rglob('*')])
    target.chmod(0o777)
    with pytest.raises(ValueError, match='root-owned'):
        catalog.read_catalog(root, protected=True)
