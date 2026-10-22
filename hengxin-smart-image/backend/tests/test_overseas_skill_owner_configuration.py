from uuid import UUID
import pytest
from app.overseas.config import load_overseas_settings
from test_overseas_configuration import configure_overseas


def test_only_explicit_overseas_owner_uuid_is_accepted(monkeypatch):
    configure_overseas(monkeypatch)
    monkeypatch.delenv('OVERSEAS_SKILL_TOGGLE_OWNER_ID', raising=False)
    monkeypatch.setenv('SKILL_TOGGLE_OWNER_ID', '00000000-0000-4000-8000-000000000005')
    assert load_overseas_settings().skill_toggle_owner_id is None
    monkeypatch.setenv('OVERSEAS_SKILL_TOGGLE_OWNER_ID', '')
    assert load_overseas_settings().skill_toggle_owner_id is None
    identity = '00000000-0000-4000-8000-000000000006'
    monkeypatch.setenv('OVERSEAS_SKILL_TOGGLE_OWNER_ID', identity)
    assert load_overseas_settings().skill_toggle_owner_id == UUID(identity)
    monkeypatch.setenv('OVERSEAS_SKILL_TOGGLE_OWNER_ID', 'a display name')
    with pytest.raises(RuntimeError, match='skill_toggle_owner_id') as error:
        load_overseas_settings()
    assert 'a display name' not in str(error.value)
