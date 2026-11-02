"""Explicit language contract, historical nulls, and immutable review evidence."""
from uuid import UUID
import pytest
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, setup, payload, create, counts, ROOT
from test_overseas_materials import materials
from test_overseas_requirements import pending, review
from test_overseas_assignment import change_roles
from test_overseas_plans import post


@pytest.mark.parametrize('language', ['en', 'de', 'fr', 'es'])
def test_language_persisted_in_create_replay_list_and_detail(overseas, language):
    client, factory, _, designer = setup(overseas)
    body = {**payload(designer), 'language': language}
    response = create(client, body)
    assert response.status_code == 201, response.text
    task = response.json()
    assert task['language'] == language
    assert create(client, body).json() == task
    assert create(client, {**body, 'language': 'de' if language != 'de' else 'en'}).status_code == 409
    assert client.get(ROOT + '/tasks/' + task['id']).json()['language'] == language
    assert client.get(ROOT + '/tasks').json()['items'][0]['language'] == language
    with factory() as session:
        assert session.get(Task, UUID(task['id'])).language == language


@pytest.mark.parametrize('language', ['missing', None, '', 'zh', 'EN', 1])
def test_invalid_language_create_has_no_side_effects(overseas, language):
    client, factory, _, designer = setup(overseas)
    body = payload(designer)
    body.pop('language')
    if language != 'missing':
        body['language'] = language
    assert create(client, body).status_code == 422
    assert counts(factory) == [0] * 5


def test_historical_null_can_be_read_reviewed_but_resubmit_requires_language(materials):
    client, factory, actor, designer, _ = materials
    task, material = pending(materials)
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).language = None
    assert client.get(ROOT + '/tasks/' + task['id']).json()['language'] is None
    change_roles(factory, actor, ('super_admin',))
    rejected = review(client, task, 'reject', '补充').json()
    assert rejected['requirementsReviews'][0]['submission']['language'] is None
    body = {**payload(designer), 'version': rejected['version'], 'materialIds': [material['id']]}
    body.pop('language')
    assert post(client, task, '/resubmit', body).status_code == 422
    for invalid in (None, '', 'zh'):
        assert post(client, task, '/resubmit', {**body, 'language': invalid}).status_code == 422
    result = post(client, task, '/resubmit', {**body, 'language': 'es'}, 'valid').json()
    assert result['language'] == 'es' and result['version'] == rejected['version'] + 1
    assert result['requirementsReviews'][0]['submission']['language'] is None
    approved = review(client, result, key='approve').json()
    assert approved['status'] == 'studio'
    assert approved['requirementsReviews'][-1]['submission']['language'] == 'es'
