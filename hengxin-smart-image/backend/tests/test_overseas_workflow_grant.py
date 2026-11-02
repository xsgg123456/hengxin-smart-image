"""Account-scoped workflow grants exercised through real isolated HTTP routes."""
from uuid import UUID, uuid4
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.core.config import get_settings
from app.overseas.auth.models import Member, MemberRole
from app.overseas.permissions import principal_for, can_access_task, task_filter, authorize_member
from app.overseas.tasks.models import Task
from test_overseas_auth import overseas, login
from test_overseas_tasks import setup, create, payload, add_member, ROOT, HEADERS
from test_overseas_materials import materials, upload, submit
from test_overseas_assignment import change_roles
from test_overseas_plans import post
from test_overseas_requirements import review


def grant(actor):
    get_settings().workflow_collaborator_member_ids = frozenset((actor,))


def relate(factory, task, actor, other, relation):
    with factory.begin() as session:
        row = session.get(Task, UUID(task['id']))
        row.created_by = actor if relation == 'created' else other
        row.designer_id = actor if relation == 'assigned' else other


def test_configuration_default_uuid_and_independent_grants(overseas, monkeypatch):
    from app.overseas.config import load_overseas_settings
    assert load_overseas_settings().workflow_collaborator_member_ids == frozenset()
    identity = uuid4()
    monkeypatch.setenv('OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS', '["' + str(identity) + '"]')
    settings = load_overseas_settings()
    assert settings.workflow_collaborator_member_ids == {identity}
    assert settings.full_access_member_ids == frozenset()
    monkeypatch.setenv('OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS', '["invalid-private-id"]')
    with pytest.raises(RuntimeError, match='workflow_collaborator_member_ids') as error:
        load_overseas_settings()
    assert 'invalid-private-id' not in str(error.value)


def test_list_detail_and_stats_keep_distinct_scopes(overseas):
    client, factory, actor, other = setup(overseas)
    grant(actor)
    tasks = {}
    for relation in ('created', 'assigned', 'unrelated'):
        task = create(client, payload(other), relation).json()
        relate(factory, task, actor, other, relation)
        tasks[relation] = task
    rows = client.get(ROOT + '/tasks?pageSize=1').json()
    assert rows['total'] == 3 and len(rows['items']) == 1
    assert client.get(ROOT + '/tasks?scope=mine').json()['total'] == 2
    for relation, task in tasks.items():
        result = client.get(ROOT + '/tasks/' + task['id']).json()
        expected = ['task.read'] if relation == 'unrelated' else [
            'task.read', 'task.design', 'task.materials.submit']
        assert result['capabilities'] == expected
    with factory() as session:
        principal = principal_for(session, session.get(Member, actor))
        assert len(list(session.scalars(select(Task.id).where(task_filter(
            principal, Task.created_by, Task.designer_id, 'stats.read'))))) == 2
    me = client.get(ROOT + '/auth/me').json()
    assert me['roles'] == ['designer'] and me['id'] == str(actor)
    assert set(me['capabilities']) == {'task.read', 'task.create', 'task.design', 'stats.read',
                                       'task.workflow.collaborate'}
    for endpoint in ('/members', '/management/settings', '/management/skills'):
        assert client.get(ROOT + endpoint).status_code == 403
    task = tasks['created']
    assert client.patch(ROOT + '/tasks/' + task['id'] + '/assignment',
        json={'version': 1, 'designerId': str(actor)},
        headers={**HEADERS, 'Idempotency-Key': 'assign'}).status_code == 403
    response = client.request('DELETE', ROOT + '/tasks/' + task['id'],
        json={'version': 1}, headers=HEADERS)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize('change', ['revoke', 'disabled', 'pending', 'directory', 'roleless', 'multi', 'unknown'])
def test_existing_session_rechecks_account_and_role(overseas, change):
    client, factory, actor, other = setup(overseas)
    grant(actor)
    task = create(client, payload(other)).json()
    relate(factory, task, actor, other, 'unrelated')
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 200
    if change == 'revoke':
        get_settings().workflow_collaborator_member_ids = frozenset()
    else:
        with factory.begin() as session:
            member = session.get(Member, actor)
            if change in ('disabled', 'pending'):
                member.status = change
            elif change == 'directory':
                member.directory_state = 'legacy_unconfirmed'
            elif change == 'roleless':
                change_roles(factory, actor, ())
            else:
                # Model constraints forbid corrupt roles; emulate legacy DB corruption.
                session.execute(text('CREATE TABLE legacy_roles AS SELECT * FROM overseas_member_roles'))
                session.execute(text('DROP TABLE overseas_member_roles'))
                session.execute(text('ALTER TABLE legacy_roles RENAME TO overseas_member_roles'))
                session.add(MemberRole(user_id=actor, role='design_manager' if change == 'multi' else 'unknown'))
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 403
    assert client.get(ROOT + '/members').status_code == 403


def test_same_name_not_granted_and_changed_role_keeps_existing_policy(overseas):
    client, factory, actor, other = setup(overseas)
    grant(actor)
    same_name = add_member(factory, name='海外成员')
    with factory() as session:
        twin = principal_for(session, session.get(Member, same_name))
        assert not twin.workflow_collaborator
        assert not can_access_task(twin, actor, other)
    task = create(client, payload(other)).json()
    change_roles(factory, actor, ('design_manager',))
    with factory() as session:
        principal = principal_for(session, session.get(Member, actor))
        assert not principal.workflow_collaborator
        assert principal.roles == {'design_manager'}
    assert client.get(ROOT + '/members').status_code == 403
    assert 'task.reassign' in client.get(ROOT + '/tasks/' + task['id']).json()['capabilities']
    change_roles(factory, actor, ('designer',))
    get_settings().workflow_collaborator_member_ids = frozenset((same_name,))
    assert 'task.design' not in client.get(ROOT + '/tasks/' + task['id']).json()['capabilities']


def test_grant_marker_tracks_revocation_but_cannot_authorize(overseas):
    client, factory, actor, _ = setup(overseas)
    marker = 'task.workflow.collaborate'
    assert marker not in client.get(ROOT + '/auth/me').json()['capabilities']
    grant(actor)
    assert marker in login(client).json()['capabilities']
    assert marker in client.get(ROOT + '/auth/me').json()['capabilities']
    with factory() as session:
        member = session.get(Member, actor)
        with pytest.raises(HTTPException) as denied:
            authorize_member(session, member, marker)
        assert denied.value.status_code == 403
    get_settings().workflow_collaborator_member_ids = frozenset()
    assert marker not in client.get(ROOT + '/auth/me').json()['capabilities']
    grant(actor)
    change_roles(factory, actor, ('design_manager',))
    assert marker not in client.get(ROOT + '/auth/me').json()['capabilities']


@pytest.mark.parametrize('relation', ['created', 'assigned', 'unrelated'])
def test_submit_review_resubmit_uses_same_capabilities(materials, relation):
    client, factory, actor, other, _ = materials
    grant(actor)
    task = create(client, payload(other)).json()
    relate(factory, task, actor, other, relation)
    material = upload(client).json()
    response = submit(client, task['id'], [material['id']])
    if relation == 'unrelated':
        assert response.status_code == 403
        assert review(client, task).status_code == 403
        assert post(client, task, '/resubmit', {
            **payload(other), 'version': 1, 'materialIds': [material['id']]}).status_code == 403
        return
    assert response.status_code == 200, response.text
    task = response.json()
    assert 'task.requirements.review' in task['capabilities']
    rejected = review(client, task, 'reject', '补全资料').json()
    assert 'task.requirements.resubmit' in rejected['capabilities']
    designer = actor if relation == 'assigned' else other
    body = {**payload(designer), 'version': rejected['version'], 'materialIds': [material['id']]}
    assert post(client, task, '/resubmit', {**body, 'designerId': str(uuid4())}).status_code == 404
    alternate = add_member(factory)
    assert post(client, task, '/resubmit', {**body, 'designerId': str(alternate)}).status_code == 403
    result = post(client, task, '/resubmit', body)
    assert result.status_code == 200, result.text
    assert post(client, task, '/resubmit', body).json() == result.json()
    assert review(client, result.json(), key='approve').status_code == 200


def test_unsubmitted_materials_remain_private(materials):
    from app.overseas.materials.models import Material
    client, factory, actor, other, _ = materials
    grant(actor)
    material = upload(client).json()
    with factory.begin() as session:
        session.get(Material, UUID(material['id'])).owner_id = other
    path = ROOT + '/materials/' + material['id']
    assert client.get(path).status_code == 403
    assert client.get(path + '/content').status_code == 403
    assert client.delete(path, headers=HEADERS).status_code == 403
    assert create(client, {**payload(actor), 'materialIds': [material['id']]}).status_code == 403


@pytest.mark.parametrize('relation', ['created', 'assigned', 'unrelated'])
@pytest.mark.skipif(os.name == 'nt', reason='Legacy output validation requires POSIX safe-open support')
def test_legacy_plan_and_picture_workflow_preserves_scope(materials, monkeypatch, tmp_path, relation):
    from app.overseas.execution import claims
    from app.overseas.generation import delivery
    from test_overseas_plans import prepared, plans, publish
    from test_overseas_pictures import jobs, generate, picture_list, action
    client, factory, actor, task = prepared(materials, monkeypatch)
    plan = plans(client, task)[0]
    publish(factory, plan)
    change_roles(factory, actor, ('designer',))
    grant(actor)
    relate(factory, task, actor, UUID(task['designer']['id']), relation)
    confirmation = post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 3}, 'confirm')
    if relation == 'unrelated':
        assert confirmation.status_code == 403
        change_roles(factory, actor, ('super_admin',))
        confirmation = post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 3}, 'confirm')
    assert confirmation.status_code == 200, confirmation.text
    monkeypatch.setattr(delivery, 'get_store', lambda: materials[-1])
    first, second = jobs(factory)
    generate(factory, first, tmp_path)
    with factory.begin() as session:
        claims.end(session, claims.locked_job(session, second), 'failed', error=True)
    change_roles(factory, actor, ('designer',))
    listing = picture_list(client, task)
    retried = post(client, task, '/generation/retry', {'version': listing['taskVersion'], 'sku': 'B'}, 'retry')
    if relation == 'unrelated':
        assert retried.status_code == 403
        picture = listing['items'][0]
        assert client.get(picture['url']).status_code == 200
        assert action(client, picture, '/approve', listing['taskVersion'], 'approve').status_code == 403
        assert action(client, picture, '/revisions', listing['taskVersion'], 'revise', note='修改', marks=[]).status_code == 403
        assert post(client, task, '/archive', {'version': listing['taskVersion']}, 'archive').status_code == 403
        return
    assert retried.status_code == 200, retried.text
    generate(factory, jobs(factory)[-1], tmp_path)
    listing = picture_list(client, task)
    first_picture, second_picture = listing['items']
    approved = action(client, first_picture, '/approve', listing['taskVersion'], 'approve-first')
    assert approved.status_code == 200, approved.text
    revised = action(client, second_picture, '/revisions', approved.json()['version'], 'revise', note='修改', marks=[])
    assert revised.status_code == 200, revised.text
    generate(factory, jobs(factory, 'revision')[-1], tmp_path, 'blue')
    listing = picture_list(client, task)
    approved = action(client, listing['items'][1], '/approve', listing['taskVersion'], 'approve-second')
    assert approved.status_code == 200, approved.text
    archived = post(client, task, '/archive', {'version': approved.json()['version']}, 'archive')
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
