"""Three-role API boundaries, ownership union, and compatibility field semantics."""
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.overseas.auth.models import MemberRole
from app.overseas.members.schemas import MemberPatch
from app.overseas.tasks.models import Task
from test_overseas_assignment import change_roles
from test_overseas_materials import materials, upload, submit
from test_overseas_plans import post
from test_overseas_requirements import pending, review
from test_overseas_tasks import overseas, setup, create, payload, ROOT, HEADERS
from membership_helpers import membership_env, files_env, post as identity_post, decide


@pytest.mark.parametrize('role', ['operator', 'operator_manager'])
def test_removed_roles_rejected_by_api_and_database(overseas, role):
    from pydantic import ValidationError
    client, factory, actor, designer = setup(overseas, ('super_admin',))
    with pytest.raises(ValidationError):
        MemberPatch(roles=[role], status='active', version=1)
    response = client.patch(ROOT + '/members/' + str(designer),
        json=dict(roles=[role], status='active', version=1), headers=HEADERS)
    assert response.status_code == 422
    assert client.get(ROOT + '/members?role=' + role).status_code == 422
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.execute(update(MemberRole).where(MemberRole.user_id == designer).values(role=role))


@pytest.mark.parametrize('role', ['operator', 'operator_manager'])
def test_application_role_boundary_keeps_domestic_operator(membership_env, role):
    env = membership_env
    application = identity_post(env, 'application').json()
    response = decide(env, application, role=role)
    allowed = env['business'] == 'domestic' and role == 'operator'
    assert response.status_code == (200 if allowed else 422), response.text
    if not allowed:
        assert identity_post(env, 'access').json()['state'] == 'pending'


@pytest.mark.parametrize('fields,expected', [({}, '说明'), ({'remarks': ''}, ''),
                                          ({'remarks': ' 新说明 '}, '新说明')])
def test_resubmit_remarks_preserve_or_clear_with_distinct_replay(materials, fields, expected):
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    change_roles(factory, actor, ('design_manager',))
    returned = review(client, task, 'reject', '补充资料').json()
    change_roles(factory, actor, ('designer',))
    body = {**payload(designer), 'version': returned['version'], 'materialIds': [original['id']]}
    body.pop('remarks')
    body.update(fields)
    result = post(client, task, '/resubmit', body, 'remarks')
    assert result.status_code == 200, result.text
    assert result.json()['remarks'] == expected
    assert result.json()['requirementsReviews'][0]['submission']['remarks'] == '说明'
    assert post(client, task, '/resubmit', body, 'remarks').json() == result.json()
    different = dict(body)
    if 'remarks' in different:
        different.pop('remarks')
    else:
        different['remarks'] = ''
    assert post(client, task, '/resubmit', different, 'remarks').status_code == 409
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).remarks == expected


def test_designer_creates_without_hidden_fields_and_cannot_review_unassigned(materials):
    client, factory, actor, designer, _ = materials
    material = upload(client).json()
    body = {**payload(designer), 'materialIds': [material['id']]}
    body.pop('market')
    body.pop('remarks')
    task = create(client, body).json()
    assert task['market'] == task['remarks'] == ''
    assert 'task.read' in task['capabilities'] and 'task.design' not in task['capabilities']
    assert review(client, task).status_code == 403
    assert client.get(ROOT + '/tasks/' + task['id']).status_code == 200


@pytest.mark.parametrize('state', ['created', 'returned'])
def test_assignment_alone_cannot_submit_or_resubmit_but_manager_can(materials, state):
    client, factory, actor, other, _ = materials
    task = create(client, payload(actor)).json()
    material = upload(client).json()
    with factory.begin() as session:
        current = session.get(Task, UUID(task['id']))
        current.created_by, current.status = other, state
    view = client.get(ROOT + '/tasks/' + task['id']).json()
    assert 'task.design' in view['capabilities']
    capability = 'task.materials.submit' if state == 'created' else 'task.requirements.resubmit'
    assert capability not in view['capabilities']

    def mutate():
        if state == 'created':
            return submit(client, task['id'], [material['id']])
        return post(client, task, '/resubmit', {
            **payload(actor), 'version': 1, 'materialIds': [material['id']]})

    assert mutate().status_code == 403
    change_roles(factory, actor, ('design_manager',))
    assert capability in client.get(ROOT + '/tasks/' + task['id']).json()['capabilities']
    response = mutate()
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'pending_review'
