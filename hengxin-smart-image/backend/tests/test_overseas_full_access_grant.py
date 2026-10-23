"""Account grants retain role/identity and reuse the existing server-side policy."""
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.overseas.auth.models import Member, MemberRole
from app.overseas.permissions import CAPABILITIES, can_access_task, principal_for
from app.overseas.management.skills import can_toggle
from app.overseas.management.models import Audit
from test_overseas_auth import overseas, seed, login, HEADERS, COOKIE_PATH
from test_overseas_tasks import add_member, create, payload


def grant(actor):
    get_settings().full_access_member_ids = frozenset((actor,))


def test_full_capabilities_real_role_and_identity_unchanged(overseas):
    client, factory, _ = overseas
    actor = seed(factory, roles=('design_manager',))
    other = add_member(factory, ('design_manager',), name='海外成员')
    grant(actor)
    result = login(client)
    assert result.status_code == 200
    assert result.json()['roles'] == ['design_manager']
    assert result.json()['id'] == str(actor)
    assert set(result.json()['capabilities']) == set(CAPABILITIES)
    with factory() as session:
        member = session.get(Member, actor)
        principal = principal_for(session, member)
        for action in CAPABILITIES:
            assert can_access_task(principal, uuid4(), uuid4(), action)
        assert not can_access_task(principal, actor, actor, 'unknown')
        assert principal_for(session, session.get(Member, other)).roles == {'design_manager'}
        assert can_toggle(member)
        assert not can_toggle(session.get(Member, other))
        assert list(session.scalars(select(MemberRole.role).where(MemberRole.user_id == actor))) == ['design_manager']
    assert client.get(COOKIE_PATH + '/members').status_code == 200
    assert client.get(COOKIE_PATH + '/management/settings').status_code == 200
    assert client.get(COOKIE_PATH + '/management/skills').json()['canToggle']
    task = create(client, payload(other))
    assert task.status_code == 201, task.text
    assert task.json()['createdBy']['id'] == str(actor)


@pytest.mark.parametrize('change', ['disabled', 'pending', 'legacy', 'roleless'])
def test_grant_never_bypasses_membership_on_existing_session(overseas, change):
    client, factory, _ = overseas
    actor = seed(factory, roles=('design_manager',))
    grant(actor)
    assert login(client).status_code == 200
    with factory.begin() as session:
        member = session.get(Member, actor)
        if change in ('disabled', 'pending'):
            member.status = change
        elif change == 'legacy':
            member.directory_state = 'legacy_unconfirmed'
        else:
            session.execute(delete(MemberRole).where(MemberRole.user_id == actor))
    for endpoint in ('/auth/me', '/members', '/management/skills'):
        assert client.get(COOKIE_PATH + endpoint).status_code == 403
    with factory() as session:
        with pytest.raises(HTTPException):
            principal_for(session, session.get(Member, actor))


def test_revoke_rechecks_existing_session_and_preserves_owner(overseas):
    client, factory, _ = overseas
    actor = seed(factory, roles=('design_manager',))
    owner = add_member(factory, ('super_admin',))
    get_settings().skill_toggle_owner_id = owner
    grant(actor)
    assert login(client).status_code == 200
    get_settings().full_access_member_ids = frozenset()
    result = client.get(COOKIE_PATH + '/auth/me').json()
    assert result['roles'] == ['design_manager']
    assert 'members.manage' not in result['capabilities']
    assert client.get(COOKIE_PATH + '/members').status_code == 403
    with factory() as session:
        assert can_toggle(session.get(Member, owner))
        assert not can_toggle(session.get(Member, actor))


def test_skill_write_audits_real_actor_and_keeps_last_admin(overseas):
    from overseas_installed_helpers import install_sample
    client, factory, _ = overseas
    actor = seed(factory, roles=('design_manager',))
    owner = add_member(factory, ('super_admin',))
    get_settings().skill_toggle_owner_id = owner
    grant(actor)
    assert login(client).status_code == 200
    item = install_sample()
    response = client.patch(COOKIE_PATH + '/management/skills/' + item['id'] + '/availability',
                            json={'enabled': True, 'version': 1}, headers=HEADERS)
    assert response.status_code == 200, response.text
    with factory() as session:
        audit = session.scalar(select(Audit))
        assert audit.actor_id == actor and audit.action == 'skill.availability'
    response = client.patch(COOKIE_PATH + '/members/' + str(owner),
                            json={'roles': ['designer'], 'status': 'active', 'version': 1}, headers=HEADERS)
    assert response.status_code == 409


def test_delegate_can_resubmit_unowned_task_without_role_change(materials, monkeypatch):
    from app.overseas.materials import parsers
    from app.overseas.tasks.models import Task
    from test_overseas_requirements import pending, review
    from test_overseas_plans import post
    from test_overseas_assignment import change_roles
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: '完整资料')
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    stranger = add_member(factory, ('operator',))
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).created_by = stranger
    change_roles(factory, actor, ('design_manager',))
    grant(actor)
    assert review(client, task, 'reject', '补充').status_code == 200
    body = {**payload(designer), 'version': 2, 'materialIds': [original['id']]}
    assert post(client, task, '/resubmit', body).status_code == 200
    assert post(client, task, '/resubmit', {**body, 'version': 3}, 'invalid-state').status_code == 409
    assert client.get(COOKIE_PATH + '/auth/me').json()['roles'] == ['design_manager']


def test_configuration_uuid_validation_and_default(overseas, monkeypatch):
    from app.overseas.config import load_overseas_settings
    assert load_overseas_settings().full_access_member_ids == frozenset()
    identity = uuid4()
    monkeypatch.setenv('OVERSEAS_FULL_ACCESS_MEMBER_IDS', '["' + str(identity) + '"]')
    assert load_overseas_settings().full_access_member_ids == {identity}
    monkeypatch.setenv('OVERSEAS_FULL_ACCESS_MEMBER_IDS', '["invalid-member"]')
    with pytest.raises(RuntimeError, match='full_access_member_ids'):
        load_overseas_settings()


from test_overseas_materials import materials
