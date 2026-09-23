from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.management.models import SettingsAuditRecord
from app.modules.tasks.models import RoundRecord
from app.modules.tasks.claims import claim
from app.resource_models import UserRecord
from files_helpers import files_env
from test_tasks import task_env, body, submit, job_for
from test_templates_skills import add_skill, identity_id

URL = '/api/v1/management/settings'


def admin(env):
    with env[1].begin() as session:
        session.get(UserRecord, env[3][0]).role = 'super_admin'


def payload(client):
    data = client.get(URL).json()
    return {k: data[k] for k in ('version', 'concurrency', 'timeoutSeconds', 'maxUploadBytes',
                                'defaultSkillIds', 'dingtalk')}


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


def test_two_hour_settings_freeze_only_new_rounds(task_env, monkeypatch):
    admin(task_env)
    client, factory, _, _ = task_env
    old = submit(task_env, key='old-hour').json()
    monkeypatch.setattr(get_settings(), 'codex_timeout_seconds', 7200)
    data = payload(client)
    saved = client.put(URL, json={**data, 'timeoutSeconds': 7200})
    assert saved.status_code == 200 and saved.json()['timeoutCapacity'] == 7200
    assert client.put(URL, json={**payload(client), 'timeoutSeconds': 7201}).status_code == 422
    new = submit(task_env, key='new-two-hours').json()
    with factory() as session:
        assert session.get(RoundRecord, UUID(old['roundId'])).execution_config['timeoutSeconds'] == 3600
        assert session.get(RoundRecord, UUID(new['roundId'])).execution_config['timeoutSeconds'] == 7200


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


def test_defaults_share_version_and_invalid_save_is_atomic(files_env):
    admin(files_env)
    client, factory, _, _ = files_env
    stale = payload(client)
    skill_id = add_skill(factory, mode='text')
    defaults = {**stale['defaultSkillIds'], 'text': skill_id}
    assert client.put('/api/v1/management/skills/defaults', json=defaults).status_code == 200
    assert client.put(URL, json=stale).status_code == 409
    current = payload(client)
    assert current['defaultSkillIds'] == {**defaults, 'text': identity_id(factory, skill_id)}
    bad = {**current, 'timeoutSeconds': 120,
           'defaultSkillIds': {**defaults, 'wallpaper': skill_id}}
    assert client.put(URL, json=bad).status_code == 422
    assert payload(client) == current
    assert client.get(URL).json()['audit'][0]['fields'] == ['defaultSkillIds']


def test_future_rounds_freeze_settings_and_upload_limit_is_enforced(task_env, monkeypatch):
    admin(task_env)
    monkeypatch.setattr(get_settings(), 'generation_concurrency', 2)
    client, factory, _, _ = task_env
    first = submit(task_env, body(task_env), key='before-config').json()
    data = payload(client)
    saved = client.put(URL, json={**data, 'concurrency': 1, 'timeoutSeconds': 120,
                                  'maxUploadBytes': 1024**2})
    assert saved.status_code == 200, saved.text
    second = submit(task_env, body(task_env), key='after-config').json()
    with factory() as session:
        old = session.get(RoundRecord, UUID(first['roundId'])).execution_config
        new = session.get(RoundRecord, UUID(second['roundId'])).execution_config
        assert old['concurrency'] == 2 and old['timeoutSeconds'] == data['timeoutSeconds']
        assert new['concurrency'] == 1 and new['timeoutSeconds'] == 120
        assert new['settingsVersion'] == saved.json()['version']
    assert claim(factory, job_for(factory, first))
    assert claim(factory, job_for(factory, second)) is None
    response = client.post('/api/v1/files', files={'file': ('large.png', b'x'*(1024**2+1), 'image/png')})
    assert response.status_code == 413
    assert '1 MiB' in response.text
