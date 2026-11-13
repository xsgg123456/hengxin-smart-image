from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.execution.models import ExecutionGate
from app.modules.domestic_studio.bindings import freeze_for_send, read_bindings, save_bindings
from app.modules.domestic_studio.installed_skills import DomesticInstalledSkills
from app.modules.domestic_studio.models import WorkspaceBinding
from app.modules.domestic_studio.policy import WORKSPACES
from app.modules.domestic_studio.skill_state import DomesticSkillState, freeze_enabled, listing, set_availability
from test_domestic_installed_skills import install_fixture


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / 'domestic'
    root.mkdir()
    install_fixture(tmp_path, root)
    engine = create_engine('sqlite://')
    for table in (ExecutionGate.__table__, WorkspaceBinding.__table__, DomesticSkillState.__table__):
        table.create(engine)
    with Session(engine) as session:
        session.add(ExecutionGate(id=1))
        session.commit()
        yield session, DomesticInstalledSkills(root, protected=False)
    engine.dispose()


def test_installed_skill_is_disabled_until_admin_enables(setup):
    session, catalog = setup
    item = listing(session, catalog)[0]
    assert item['enabled'] is False
    with pytest.raises(HTTPException) as error:
        freeze_enabled(session, catalog, item['id'])
    assert error.value.status_code == 422
    assert set_availability(session, catalog, item['id'], True, 1)[0]['enabled'] is True
    assert freeze_enabled(session, catalog, item['id'])['skill']['id'] == item['id']


def test_bound_skill_cannot_be_disabled_and_freezes_verified_package(setup):
    session, catalog = setup
    item = listing(session, catalog)[0]
    set_availability(session, catalog, item['id'], True, 1)
    save_bindings(session, dict.fromkeys(WORKSPACES) | {'camera': item['id']},
                  lambda identity: freeze_enabled(session, catalog, identity), expected=read_bindings(session))
    result = freeze_for_send(session, 'camera', None, lambda identity: freeze_enabled(session, catalog, identity))
    assert result['skill']['id'] == item['id']
    with pytest.raises(HTTPException) as error:
        set_availability(session, catalog, item['id'], False, 2)
    assert error.value.status_code == 409
    assert listing(session, catalog)[0]['enabled'] is True
    save_bindings(session, dict.fromkeys(WORKSPACES), lambda _: None, expected=read_bindings(session))
    assert set_availability(session, catalog, item['id'], False, 2)[0]['enabled'] is False


def test_invalid_or_tampered_skill_never_looks_enabled(setup):
    session, catalog = setup
    with pytest.raises(HTTPException) as error:
        set_availability(session, catalog, 'not-installed', True, 1)
    assert error.value.status_code == 404
    with patch.object(catalog, '_catalog', side_effect=HTTPException(503, 'invalid')):
        with pytest.raises(HTTPException) as error:
            listing(session, catalog)
        assert error.value.status_code == 503
