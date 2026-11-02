"""Persistent platform editing and admission contracts against isolated real installs."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.config import get_settings
from app.overseas.execution.models import Job
from app.overseas.management.installed_catalog import frozen_package
from app.overseas.management.models import Audit, InstalledSkillAvailability
from app.overseas.tasks.models import Task
from overseas_installed_helpers import install_sample, enable_sample
from test_overseas_assignment import change_roles
from test_overseas_management import MANAGE
from test_overseas_materials import materials
from test_overseas_skill_availability import toggle, audit_count
from test_overseas_studio import studio, send, finish
from test_overseas_tasks import overseas, setup, HEADERS, ROOT, create, payload


def patch(client, *items, headers=HEADERS):
    return client.patch(MANAGE + '/skills/platforms', json={'items': list(items)}, headers=headers)


def change(item, platforms, version=1):
    return {'id': item['id'], 'version': version, 'platforms': platforms}


def test_management_permission_distinct_from_toggle_and_persists_across_install(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    item = install_sample()
    enable_sample(factory, platforms=[])
    before = client.get(MANAGE + '/skills').json()
    assert before['canToggle'] is False and before['canManagePlatforms'] is True
    assert toggle(client, item, headers=HEADERS).status_code == 403
    result = patch(client, change(item, ['Amazon', 'Walmart']))
    assert result.status_code == 200, result.text
    assert result.json()['items'] == [{**item, 'platforms': ['Amazon', 'Walmart'], 'enabled': True, 'version': 2}]
    install_sample(content='new installed package')
    assert client.get(MANAGE + '/skills').json() == result.json()
    with factory() as session:
        record = session.scalar(select(Audit))
        assert (record.actor_id, record.action, record.target) == (actor, 'skill.platforms', item['name'])
        assert record.before == {'platforms': [], 'version': 1}
        assert record.after == {'platforms': ['Amazon', 'Walmart'], 'version': 2}
    assert patch(client, change(item, [], 2)).json()['items'][0]['platforms'] == []
    change_roles(factory, actor, ('designer',))
    assert patch(client, change(item, ['Amazon'], 3)).status_code == 403
    assert audit_count(factory) == 2


def test_batch_conflict_and_unknown_install_leave_all_rows_and_audits_untouched(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    first, second = install_sample(), install_sample('second')
    baseline = client.get(MANAGE + '/skills').json()
    assert patch(client, change(first, ['Amazon']), change(second, ['Walmart'], 99)).status_code == 409
    assert patch(client, change(first, ['Amazon']), change({'id': str(uuid4())}, [])).status_code == 404
    assert client.get(MANAGE + '/skills').json() == baseline
    assert audit_count(factory) == 0
    edited = patch(client, change(first, ['Amazon']), change(second, ['Walmart']))
    assert edited.status_code == 200
    assert audit_count(factory) == 2
    assert all(item['version'] == 2 and item['enabled'] is False for item in edited.json()['items'])
    # Shared version protects a fresh platform edit from a stale switch and vice versa.
    assert toggle(client, first, headers=HEADERS).status_code == 409
    assert toggle(client, first, version=2, headers=HEADERS).status_code == 200
    assert patch(client, change(first, [], 2)).status_code == 409
    assert client.get(MANAGE + '/skills').json()['items'][0]['platforms'] == ['Amazon']


def test_mid_batch_database_failure_rolls_back_state_and_audit(overseas):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    first, second = install_sample(), install_sample('second')
    before = client.get(MANAGE + '/skills').json()
    writes = []

    def fail_second_audit(mapper, connection, target):
        writes.append(target.target)
        if len(writes) == 2:
            raise RuntimeError('injected audit failure')

    event.listen(Audit, 'before_insert', fail_second_audit)
    try:
        with pytest.raises(RuntimeError, match='injected audit failure'):
            patch(client, change(first, ['Amazon']), change(second, ['Walmart']))
    finally:
        event.remove(Audit, 'before_insert', fail_second_audit)
    assert len(writes) == 2
    assert client.get(MANAGE + '/skills').json() == before
    assert audit_count(factory) == 0


@pytest.mark.parametrize('invalid', [
    [], [{'id': 'not-uuid', 'version': 1, 'platforms': []}],
    [{'id': str(uuid4()), 'version': True, 'platforms': []}],
    [{'id': str(uuid4()), 'version': '1', 'platforms': []}],
    [{'id': str(uuid4()), 'version': 0, 'platforms': []}],
    [{'id': str(uuid4()), 'version': 1, 'platforms': ['TikTok Shop']}],
    [{'id': str(uuid4()), 'version': 1, 'platforms': ['Amazon', 'Amazon']}],
    [{'id': str(uuid4()), 'version': 1, 'platforms': 'Amazon'}],
    [{'id': str(uuid4()), 'version': 1, 'platforms': None}],
    [{'id': str(uuid4()), 'version': 1, 'platforms': [], 'enabled': True}],
])
def test_invalid_batch_is_rejected_without_writes(overseas, invalid):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    install_sample()
    assert patch(client, *invalid).status_code == 422
    assert audit_count(factory) == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(InstalledSkillAvailability)) == 0


def test_duplicate_ids_csrf_and_unknown_install_default(overseas):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    item = install_sample('brand-new-package')
    assert client.get(MANAGE + '/skills').json()['items'] == [
        {**item, 'enabled': False, 'version': 1, 'platforms': []}]
    edit = change(item, ['Amazon'])
    assert patch(client, edit, edit).status_code == 422
    assert patch(client, edit, headers={}).status_code == 403
    assert patch(client, edit, headers={**HEADERS, 'Origin': 'https://evil.example'}).status_code == 403
    assert audit_count(factory) == 0


def test_filter_recheck_replay_and_immutable_frozen_round(studio):
    client, factory, _, task, _, _ = studio
    match = install_sample(files={'assets/font.ttf': b'original font'})
    other = install_sample('other')
    ungrouped = install_sample('ungrouped')
    disabled = install_sample('disabled')
    enable_sample(factory, platforms=['Amazon', 'Wayfair'])
    enable_sample(factory, 'other', ['Walmart'])
    enable_sample(factory, 'ungrouped', [])
    path = ROOT + '/tasks/' + task['id'] + '/studio'
    assert client.get(path).json()['skills'] == [match]
    for unavailable in (other, ungrouped, disabled):
        assert send(client, task, skillId=unavailable['id']).status_code == 422
    first = send(client, task, skillId=match['id'])
    assert first.status_code == 200, first.text
    with factory() as session:
        frozen = session.scalar(select(Job)).payload['skill']
    package = frozen_package(frozen)
    assert patch(client, change(match, ['Wayfair'])).status_code == 200
    assert client.get(path).json()['skills'] == []
    replay = send(client, task, skillId=match['id'])
    assert replay.status_code == 200 and replay.json()['turns'] == first.json()['turns']
    finish(factory, first.json()['turns'][0])
    assert send(client, task, key='fresh', skillId=match['id']).status_code == 422
    assert frozen_package(frozen).files == package.files
    assert send(client, task, key='without-skill').status_code == 200
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 2


@pytest.mark.parametrize('platform', ['Wayfair', 'Mercado Libre', 'Walmart', 'The Home Depot', 'Shopee', 'Amazon'])
def test_all_target_platforms_create_and_filter(studio, platform):
    client, factory, _, task, _, _ = studio
    assert create(client, {**payload(UUID(task['designer']['id'])), 'platform': platform}, 'new-platform').status_code == 201
    item = install_sample()
    enable_sample(factory, platforms=[platform])
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).platform = platform
    assert send(client, task, skillId=item['id']).status_code == 200


def test_historical_platform_stays_unchanged_with_no_skill_path(studio):
    client, factory, _, task, _, _ = studio
    install_sample()
    enable_sample(factory)
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).platform = 'TikTok Shop'
    response = send(client, task)
    assert response.status_code == 200 and response.json()['skills'] == []
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).platform == 'TikTok Shop'
