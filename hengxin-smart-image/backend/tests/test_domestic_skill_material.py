"""The domestic runner uses domestic immutable bytes and the shared cache."""
import pytest
from fastapi import HTTPException

from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.modules.domestic_studio.skill_material import prepare
from test_domestic_installed_skills import install_fixture
from test_studio_skill_cache import new_workspace


def test_domestic_frozen_skill_uses_private_cache_without_overseas_root(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    catalog = DomesticInstalledSkills(root, protected=False)
    frozen = catalog.freeze(catalog.list()[0]['id'])
    expected = catalog.frozen_package(frozen)
    first = new_workspace(tmp_path / 'work')
    prepare(frozen, first, catalog)
    assert first.use_skill
    assert first.skill_name == expected.name
    assert {path.relative_to(first.local_skill).as_posix(): path.read_bytes()
            for path in first.local_skill.rglob('*') if path.is_file()} == expected.files
    again = new_workspace(tmp_path / 'work', first.home.parent.name)
    prepare(frozen, again, catalog)
    assert again.local_skill == first.local_skill


def test_domestic_skill_rejects_wrong_snapshot_before_use(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    catalog = DomesticInstalledSkills(root, protected=False)
    frozen = catalog.freeze(catalog.list()[0]['id']) | {'checksum': '0' * 64}
    workspace = new_workspace(tmp_path / 'work')
    with pytest.raises(HTTPException) as error:
        prepare(frozen, workspace, catalog)
    assert error.value.status_code == 503
    assert workspace.local_skill is None
    assert not (workspace.home.parent / 'skill-cache').exists()
