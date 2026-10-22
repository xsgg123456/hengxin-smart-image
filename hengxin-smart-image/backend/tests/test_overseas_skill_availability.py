"""HTTP availability contracts with isolated storage, accounts and database."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.execution.models import Job
from app.overseas.management.installed_catalog import frozen_package
from app.overseas.management.models import Audit, InstalledSkillAvailability
from overseas_installed_helpers import install_sample
from test_overseas_assignment import change_roles
from test_overseas_management import MANAGE, config
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish
from test_overseas_tasks import overseas, setup, add_member, HEADERS, ROOT


def toggle(client, item, enabled=True, version=1, **kwargs):
    return client.patch(MANAGE + '/skills/' + item['id'] + '/availability',
                        json={'enabled': enabled, 'version': version}, **kwargs)


def audit_count(factory):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(Audit))


def test_owner_persistent_state_survives_refresh_install_update_and_disable(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    assert client.get(MANAGE + '/skills').json() == {
        'items': [{**item, 'enabled': False, 'version': 1}], 'canToggle': True}
    enabled = toggle(client, item, headers=HEADERS)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()['items'] == [{**item, 'enabled': True, 'version': 2}]
    assert client.get(MANAGE + '/skills').json() == enabled.json()
    install_sample(content='upgraded')
    extra = install_sample('new-installation')
    refreshed = client.get(MANAGE + '/skills').json()
    by_name = {entry['name']: entry for entry in refreshed['items']}
    assert by_name[item['name']] == {**item, 'enabled': True, 'version': 2}
    assert by_name[extra['name']] == {**extra, 'enabled': False, 'version': 1}
    assert toggle(client, item, False, 2, headers=HEADERS).status_code == 200
    install_sample(content='upgraded again')
    by_name = {entry['name']: entry for entry in client.get(MANAGE + '/skills').json()['items']}
    assert by_name[item['name']]['enabled'] is False
    assert by_name[item['name']]['version'] == 3
    with factory() as session:
        row = session.get(InstalledSkillAvailability, 'sample')
        assert (row.enabled, row.version) == (False, 3)
        assert session.get(InstalledSkillAvailability, 'new-installation') is None
        audits = session.scalars(select(Audit).order_by(Audit.created_at)).all()
        assert [(a.actor_id, a.action, a.target) for a in audits] == [
            (actor, 'skill.availability', 'sample')] * 2
        assert audits[0].before == {'enabled': False, 'version': 1}
        assert audits[0].after == audits[1].before == {'enabled': True, 'version': 2}
        assert audits[1].after == {'enabled': False, 'version': 3}


@pytest.mark.parametrize('owner_mode', ['unset', 'same_name_admin', 'owner_without_permission'])
def test_owner_identity_and_original_permission_both_required(overseas, owner_mode):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    item = install_sample()
    owner = None
    if owner_mode == 'same_name_admin':
        with factory() as session:
            name = session.get(Member, actor).name
        owner = add_member(factory, ('super_admin',), name=name)
    elif owner_mode == 'owner_without_permission':
        owner = actor
        change_roles(factory, actor, ('design_manager',))
    get_settings().skill_toggle_owner_id = owner
    listing = client.get(MANAGE + '/skills')
    if owner_mode == 'owner_without_permission':
        assert listing.status_code == 403
    else:
        assert listing.status_code == 200 and listing.json()['canToggle'] is False
    assert toggle(client, item, headers=HEADERS).status_code == 403
    assert audit_count(factory) == 0
    with factory() as session:
        assert session.get(InstalledSkillAvailability, item['name']) is None


@pytest.mark.parametrize('body', [
    {}, {'enabled': True}, {'version': 1}, {'enabled': 'true', 'version': 1},
    {'enabled': 1, 'version': 1}, {'enabled': None, 'version': 1},
    {'enabled': True, 'version': True}, {'enabled': True, 'version': '1'},
    {'enabled': True, 'version': 0}, {'enabled': True, 'version': 1.0},
    {'enabled': True, 'version': 1, 'ownerId': str(uuid4())},
])
def test_toggle_body_is_strict_and_invalid_write_is_atomic(overseas, body):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    response = client.patch(MANAGE + '/skills/' + item['id'] + '/availability',
                            json=body, headers=HEADERS)
    assert response.status_code == 422, response.text
    assert audit_count(factory) == 0
    assert client.get(MANAGE + '/skills').json()['items'][0]['enabled'] is False


def test_csrf_missing_install_and_stale_version_do_not_write_audits(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    assert toggle(client, item).status_code == 403
    assert toggle(client, item, headers={**HEADERS, 'Origin': 'https://evil.example'}).status_code == 403
    assert toggle(client, {'id': str(uuid4())}, headers=HEADERS).status_code == 404
    assert toggle(client, item, version=2, headers=HEADERS).status_code == 409
    assert audit_count(factory) == 0
    assert toggle(client, item, headers=HEADERS).status_code == 200
    assert toggle(client, item, False, headers=HEADERS).status_code == 409
    assert audit_count(factory) == 1
    assert client.get(MANAGE + '/skills').json()['items'][0]['enabled'] is True


def test_settings_cannot_replace_owner_or_select_disabled_skill(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    before = client.get(MANAGE + '/settings').json()
    for field in ('skillToggleOwnerId', 'skill_toggle_owner_id'):
        assert client.patch(MANAGE + '/settings', json=config(client, **{field: str(uuid4())}),
                            headers=HEADERS).status_code == 422
    body = config(client, defaults={'analysis': item['id'], 'generation': None, 'revision': None})
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 422
    assert client.get(MANAGE + '/settings').json() == before
    assert get_settings().skill_toggle_owner_id == actor
    assert audit_count(factory) == 0


def test_disabled_skill_filters_studio_and_blocks_new_keys_but_preserves_frozen_replay(studio):
    client, factory, actor, task, _, _ = studio
    get_settings().skill_toggle_owner_id = actor
    item = install_sample()
    other = install_sample('disabled')
    path = ROOT + '/tasks/' + task['id'] + '/studio'
    assert client.get(path).json()['skills'] == []
    assert send(client, task, skillId=item['id']).status_code == 422
    assert toggle(client, item, headers=HEADERS).status_code == 200
    assert client.get(path).json()['skills'] == [item]
    assert len(client.get(MANAGE + '/skills').json()['items']) == 2
    first = send(client, task, skillId=item['id'])
    assert first.status_code == 200, first.text
    with factory() as session:
        frozen = session.scalar(select(Job)).payload['skill']
    original_bytes = frozen_package(frozen).files['SKILL.md']
    assert toggle(client, item, False, 2, headers=HEADERS).status_code == 200
    assert client.get(path).json()['skills'] == []
    replay = send(client, task, skillId=item['id'])
    assert replay.status_code == 200
    assert replay.json()['turns'] == first.json()['turns']
    assert replay.json()['skills'] == []
    assert frozen_package(frozen).files['SKILL.md'] == original_bytes
    # Already queued work remains claimable and can complete after disabling.
    finish(factory, first.json()['turns'][0])
    assert send(client, task, key='new-key', skillId=item['id']).status_code == 422
    assert send(client, task, key='other-key', skillId=other['id']).status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1
    assert client.get(path).json()['turns'][0]['status'] == 'succeeded'
