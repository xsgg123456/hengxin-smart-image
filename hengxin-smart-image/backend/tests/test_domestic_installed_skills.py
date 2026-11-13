import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.overseas.management import skill_install
from app.overseas.management.installed_catalog import package_directory, release_manifest


def install_fixture(tmp_path, root, name='camera-test', body='original', files=None):
    package = tmp_path / 'source' / name
    package.mkdir(parents=True)
    (package / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: 用于测试\n---\n\n# 测试 Skill\n\n{body}', encoding='utf-8')
    for path, data in (files or {}).items():
        target = package / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps([{'name': name, 'source': name, 'displayName': '测试 Skill'}]), encoding='utf-8')
    output = tmp_path / 'bundle'
    result = skill_install.bundle(tmp_path / 'source', mapping, output)
    with patch.object(skill_install, 'root_config', return_value=(root, False)):
        skill_install.install(result['path'])


def test_empty_installation_does_not_create_demo_skills(tmp_path):
    catalog = DomesticInstalledSkills(tmp_path, protected=False)
    assert catalog.list() == []
    with pytest.raises(HTTPException) as error:
        catalog.freeze('missing')
    assert error.value.status_code == 422


def test_reuses_verified_complete_overseas_package_reader(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root, files={'assets/reference.png': b'local test bytes'})
    catalog = DomesticInstalledSkills(root, protected=False)
    items = catalog.list()
    assert len(items) == 1
    assert items[0]['name'] == 'camera-test'
    snapshot = catalog.freeze(items[0]['id'])
    package = catalog.frozen_package(snapshot)
    assert package.files['assets/reference.png'] == b'local test bytes'
    assert package.files['SKILL.md'].decode('utf-8').endswith('original')


def test_frozen_identity_and_checksum_cannot_be_swapped(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    catalog = DomesticInstalledSkills(root, protected=False)
    snapshot = catalog.freeze(catalog.list()[0]['id'])
    for override in ({'id': 'other'}, {'checksum': '0' * 64}, {'name': 'other'}):
        with pytest.raises(HTTPException) as error:
            catalog.frozen_package(snapshot | override)
        assert error.value.status_code == 503


def test_bad_or_unindexed_directory_is_not_reported_as_empty(tmp_path):
    (tmp_path / 'unindexed-file').write_text('unindexed', encoding='utf-8')
    with pytest.raises(HTTPException) as error:
        DomesticInstalledSkills(tmp_path, protected=False).list()
    assert error.value.status_code == 503


def test_altered_installed_file_fails_integrity_check(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root, files={'assets/reference.png': b'original'})
    catalog = DomesticInstalledSkills(root, protected=False)
    snapshot = catalog.freeze(catalog.list()[0]['id'])
    release, manifest = release_manifest(root, snapshot['installedRelease'])
    package = package_directory(release, manifest['items'][0])
    (package / 'assets' / 'reference.png').write_bytes(b'altered')
    with pytest.raises(HTTPException) as error:
        catalog.frozen_package(snapshot)
    assert error.value.status_code == 503


def test_production_root_cannot_point_at_overseas_or_arbitrary_path(tmp_path):
    for path in (tmp_path, '/var/lib/hengxin-overseas/local-skills'):
        with pytest.raises(ValueError, match='not approved|overseas root'):
            DomesticInstalledSkills(path, protected=True)


def test_overseas_root_is_rejected_even_without_protected_mode():
    with pytest.raises(ValueError, match='overseas root'):
        DomesticInstalledSkills('/var/lib/hengxin-overseas/local-skills', protected=False)


def test_production_cannot_disable_protected_directory_validation(tmp_path):
    with patch('app.modules.domestic_studio.installed_skills.get_settings') as settings:
        settings.return_value.app_env = 'production'
        with pytest.raises(ValueError, match='must be protected'):
            DomesticInstalledSkills(tmp_path, protected=False)
