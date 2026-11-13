from fastapi import HTTPException
import pytest

from app.modules.domestic_studio.policy import (
    WORKSPACES, freeze_bound_skill, require_archive_workspace, require_workspace,
)


@pytest.mark.parametrize('workspace', ['camera', 'case'])
def test_new_product_workspaces_allow_archive(workspace):
    assert require_archive_workspace(workspace) is None


@pytest.mark.parametrize('workspace', ['product', 'scene', 'phone'])
def test_product_replacement_never_allows_archive(workspace):
    with pytest.raises(HTTPException) as error:
        require_archive_workspace(workspace)
    assert error.value.status_code == 403


@pytest.mark.parametrize('workspace', ['', 'camera/other', 'Camera', 'overseas', 'archive'])
def test_unknown_workspace_never_inherits_permission(workspace):
    with pytest.raises(HTTPException) as error:
        require_workspace(workspace)
    assert error.value.status_code == 404


@pytest.mark.parametrize('workspace', list(WORKSPACES))
def test_only_trusted_binding_is_frozen(workspace):
    calls = []
    def freeze(identity):
        calls.append(identity)
        return {'skill': {'id': identity, 'checksum': 'installed-snapshot'}}

    result = freeze_bound_skill(workspace, 'trusted-skill', 'trusted-skill', freeze)
    assert calls == ['trusted-skill']
    assert result['skill']['checksum'] == 'installed-snapshot'


@pytest.mark.parametrize('requested', ['', 'other-skill'])
def test_client_cannot_override_or_supply_skill(requested):
    with pytest.raises(HTTPException) as error:
        freeze_bound_skill('camera', 'trusted-skill', requested, lambda _: pytest.fail('must not freeze'))
    assert error.value.status_code == 409


@pytest.mark.parametrize('binding', [None, '', '  '])
def test_unbound_workspace_has_no_fallback_skill(binding):
    assert freeze_bound_skill('case', binding, None, lambda _: pytest.fail('must not freeze')) == {
        'skillSelection': 'none', 'skill': None}


def test_missing_frozen_skill_never_falls_back_to_a_default():
    with pytest.raises(HTTPException) as error:
        freeze_bound_skill('camera', 'unavailable', 'unavailable', lambda _: {'skill': None})
    assert error.value.status_code == 409


def test_frozen_skill_identity_must_match_binding():
    with pytest.raises(HTTPException) as error:
        freeze_bound_skill('camera', 'trusted', 'trusted', lambda _: {'skill': {'id': 'other'}})
    assert error.value.status_code == 409


def test_installed_catalog_errors_are_not_silently_swallowed():
    def unavailable(_identity):
        raise HTTPException(422, 'Skill 已停用')

    with pytest.raises(HTTPException) as error:
        freeze_bound_skill('phone', 'disabled-skill', 'disabled-skill', unavailable)
    assert error.value.status_code == 422
