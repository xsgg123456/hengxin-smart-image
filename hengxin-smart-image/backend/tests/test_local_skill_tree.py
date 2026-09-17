import hashlib
from pathlib import Path

import pytest

from app.modules.skills import local_tree


@pytest.fixture
def publication(tmp_path, monkeypatch):
    # Only the portable metadata/hash unit tests mock permissions. Linux tests do not.
    monkeypatch.setattr(local_tree, 'protected', lambda path, info: None)
    path = tmp_path / 'demo' / '1.0.0'
    path.mkdir(parents=True)
    (path / 'SKILL.md').write_text('---\nname: demo\ndescription: example\n---\n', encoding='utf-8')
    return tmp_path, path


def test_tree_hash_covers_scripts_empty_directories_and_freezes(publication):
    root, path = publication
    first = local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')
    (path / 'scripts').mkdir()
    second = local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')
    assert second.checksum != first.checksum
    (path / 'scripts/a.py').write_text('raise RuntimeError("must never run")')
    third = local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')
    assert third.checksum != second.checksum
    with pytest.raises(ValueError, match='内容已变化'):
        local_tree.inspect_tree(root, 'demo', 'text', '1.0.0', first.checksum)


def test_missing_wrong_metadata_and_size(publication, monkeypatch):
    root, path = publication
    with pytest.raises(ValueError, match='未部署'):
        local_tree.inspect_tree(root, 'demo', 'text', '2.0.0')
    (path / 'hengxin-skill.json').write_text('{"mode":"product"}')
    with pytest.raises(ValueError, match='不匹配'):
        local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')
    (path / 'hengxin-skill.json').unlink()
    monkeypatch.setattr(local_tree, 'MAX_ZIP', 1)
    with pytest.raises(ValueError, match='大小'):
        local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')


def test_local_build_metadata_is_validated_and_accepted(publication):
    root, path = publication
    published = path.with_name('1.0.0+build.1')
    path.rename(published)
    (published / 'SKILL.md').write_text('---\nname: demo\ndescription: test\nversion: 1.0.0+build.1\n---\n')
    (published / 'hengxin-skill.json').write_text('{"version":"1.0.0+build.1"}')
    tree = local_tree.inspect_tree(root, 'demo', 'text', '1.0.0+build.1')
    assert tree.path == published and tree.checksum


@pytest.mark.parametrize('version', ['01.0.0', '1.0.0-alpha..1', '1.0.0-01'])
def test_local_metadata_strictness_preserves_legacy_zip_validation(publication, version):
    from app.modules.skills.package_validator import validate_files
    files = {'SKILL.md': b'---\nname: demo\ndescription: test\n---\n'}
    assert validate_files(files, 'text', version, 'checksum').name == 'demo'
    with pytest.raises(ValueError, match='SemVer'):
        local_tree.inspect_tree(publication[0], 'demo', 'text', version)


@pytest.mark.parametrize('version', ['01.0.0', '1.0.0-alpha..1', '1.0.0-01'])
def test_local_manifest_must_match_strict_registered_version(publication, version):
    import json
    root, path = publication
    (path / 'hengxin-skill.json').write_text(json.dumps({'version': version}))
    with pytest.raises(ValueError, match='不匹配'):
        local_tree.inspect_tree(root, 'demo', 'text', '1.0.0')
