"""Legacy APP_ENV must not disable protections for deployed domestic Studio."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.domestic_studio import maintenance_lock, management_router, protected, skill_publication
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills


def test_legacy_development_configuration_enforces_roots_socket_and_shared_lock(tmp_path, monkeypatch):
    settings = SimpleNamespace(app_env='development', codex_execution_root=str(tmp_path))
    monkeypatch.setenv('DOMESTIC_STUDIO_PROTECTED', '1')
    monkeypatch.setattr(management_router, 'get_settings', lambda: settings)
    monkeypatch.setenv('DOMESTIC_SKILL_ROOT', str(tmp_path))
    monkeypatch.setenv('DOMESTIC_STUDIO_LOCK_ROOT', str(tmp_path))
    monkeypatch.setenv('DOMESTIC_SKILL_PUBLISH_SOCKET', '/tmp/unapproved.sock')
    assert protected.enabled(settings)
    with pytest.raises(HTTPException) as error:
        management_router.get_catalog()
    assert error.value.status_code == 503
    with pytest.raises(HTTPException) as error:
        management_router.publisher_socket()
    assert error.value.status_code == 503
    with pytest.raises(ValueError, match='shared lock directory'):
        with maintenance_lock.hold(settings, uuid4()):
            pass
    with pytest.raises(ValueError, match='must be protected'):
        DomesticInstalledSkills(tmp_path, protected=False)


def test_protected_management_rejects_development_identity(monkeypatch):
    settings = SimpleNamespace(app_env='development')
    monkeypatch.setenv('DOMESTIC_STUDIO_PROTECTED', '1')
    monkeypatch.setattr(skill_publication, 'get_settings', lambda: settings)
    monkeypatch.setattr(skill_publication, 'lock_permissions', lambda session: None)
    actor = SimpleNamespace(status='active', role='super_admin', directory_state='enrolled',
                            identity_source='development')
    session = SimpleNamespace(scalar=lambda query: actor)
    with pytest.raises(HTTPException) as error:
        skill_publication.authorize(session, uuid4())
    assert error.value.status_code == 403
    actor.identity_source = 'dingtalk'
    assert skill_publication.authorize(session, uuid4()) is actor


def test_production_mode_and_invalid_protection_flag_fail_closed(monkeypatch):
    monkeypatch.setenv('DOMESTIC_STUDIO_PROTECTED', '0')
    assert protected.enabled(SimpleNamespace(app_env='production'))
    monkeypatch.setenv('DOMESTIC_STUDIO_PROTECTED', 'unexpected')
    with pytest.raises(ValueError, match='Invalid'):
        protected.enabled(SimpleNamespace(app_env='development'))
