"""Optional site input preserves existing task data and resubmission semantics."""
from uuid import UUID

import pytest

from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, setup, create, payload, ROOT
from test_overseas_materials import materials
from test_overseas_requirements import pending, review
from test_overseas_assignment import change_roles
from test_overseas_plans import post


@pytest.mark.parametrize('fields,expected', [
    ({}, ''), ({'market': ''}, ''), ({'market': '  '}, ''),
    ({'market': ' 美国 '}, '美国'), ({'market': 'x' * 60}, 'x' * 60),
])
def test_create_accepts_optional_site_and_persists_it(overseas, fields, expected):
    client, factory, _, designer = setup(overseas)
    body = payload(designer)
    body.pop('market')
    body.update(fields)
    response = create(client, body)
    assert response.status_code == 201, response.text
    task = response.json()
    assert task['market'] == expected and task['platform'] == 'Amazon'
    assert create(client, body).json() == task
    assert client.get(ROOT + '/tasks/' + task['id']).json()['market'] == expected
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).market == expected


@pytest.mark.parametrize('fields', [
    {'market': 'x' * 61}, {'market': None}, {'market': 7},
    {'platform': ''}, {'brand': ''}, {'designerId': ''}, {'skus': []},
])
def test_other_validation_and_site_type_limits_remain(overseas, fields):
    client, _, _, designer = setup(overseas)
    assert create(client, {**payload(designer), 'market': '', **fields}).status_code == 422


@pytest.mark.parametrize('fields,expected', [
    ({}, '美国'), ({'market': ''}, ''), ({'market': ' 加拿大 '}, '加拿大'),
])
def test_resubmit_preserves_omitted_site_and_distinguishes_empty_request(materials, fields, expected):
    client, factory, actor, designer, _ = materials
    task, material = pending(materials)
    change_roles(factory, actor, ('super_admin',))
    returned = review(client, task, 'reject', '补全图需').json()
    body = {**payload(designer), 'version': returned['version'], 'materialIds': [material['id']]}
    body.pop('market')
    body.update(fields)
    response = post(client, task, '/resubmit', body, 'site-resubmit')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['market'] == expected and result['status'] == 'pending_review'
    assert result['requirementsReviews'][0]['submission']['market'] == '美国'
    assert post(client, task, '/resubmit', body, 'site-resubmit').json() == result
    different = dict(body)
    if 'market' in different:
        different.pop('market')
    else:
        different['market'] = ''
    assert post(client, task, '/resubmit', different, 'site-resubmit').status_code == 409
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).market == expected
