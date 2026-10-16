from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.management.models import SettingsAuditRecord
from app.resource_models import UserRecord
from files_helpers import files_env

URL = '/api/v1/management/settings'


def admin(env):
    with env[1].begin() as session:
        session.get(UserRecord, env[3][0]).role = 'super_admin'


def payload(client):
    data = client.get(URL).json()
    return {k: data[k] for k in ('version', 'concurrency', 'timeoutSeconds', 'maxUploadBytes',
                                'dingtalk')}


def test_persistent_settings_conflict_and_audit(files_env):
    admin(files_env)
    client, factory, _, _ = files_env
    original = payload(client)
    first = client.put(URL, json={**original, 'timeoutSeconds': 120})
    assert first.status_code == 200, first.text
    assert first.json()['version'] == original['version'] + 1
    assert client.get(URL).json()['timeoutSeconds'] == 120
    assert client.put(URL, json=original).status_code == 409
    same = client.put(URL, json=payload(client))
    assert same.json()['version'] == first.json()['version']
    assert same.json()['audit'][0]['fields'] == ['timeoutSeconds']
    with factory() as session:
        audit = session.scalar(select(SettingsAuditRecord))
        assert audit.before['timeoutSeconds'] == original['timeoutSeconds']
        assert audit.after['timeoutSeconds'] == 120
        assert audit.operator_id == files_env[3][0]




@pytest.mark.parametrize('role', ['operator', 'designer', 'design_manager'])
def test_settings_admin_only(files_env, role):
    admin(files_env)
    data = payload(files_env[0])
    with files_env[1].begin() as session:
        session.get(UserRecord, files_env[3][0]).role = role
    assert files_env[0].get(URL).status_code == 403
    assert files_env[0].put(URL, json=data).status_code == 403


@pytest.mark.parametrize('change', [dict(concurrency=0), dict(concurrency=11),
    dict(timeoutSeconds=59), dict(timeoutSeconds=3601), dict(maxUploadBytes=0),
    dict(maxUploadBytes=11*1024**2), dict(concurrency=True), dict(timeoutSeconds=60.5)])
def test_reject_invalid_config_without_audit(files_env, change):
    admin(files_env)
    before = payload(files_env[0])
    response = files_env[0].put(URL, json={**before, **change})
    assert response.status_code == 422
    assert payload(files_env[0]) == before
    assert files_env[0].get(URL).json()['audit'] == []


def test_capacity_and_dingtalk_are_deployment_limits(files_env, monkeypatch):
    admin(files_env)
    monkeypatch.setattr(get_settings(), 'generation_concurrency', 2)
    monkeypatch.setattr(get_settings(), 'codex_timeout_seconds', 600)
    data = payload(files_env[0])
    assert files_env[0].get(URL).json()['capacity'] == 2
    assert files_env[0].get(URL).json()['timeoutCapacity'] == 600
    assert files_env[0].put(URL, json={**data, 'timeoutSeconds': 601}).status_code == 422
    assert files_env[0].put(URL, json={**data, 'concurrency': 3}).status_code == 422
    data['dingtalk']['corpId'] = 'cannot-edit'
    assert files_env[0].put(URL, json=data).status_code == 422




