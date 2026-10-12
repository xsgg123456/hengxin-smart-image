from datetime import timedelta
from uuid import UUID
import pytest
from sqlalchemy import func, select
from app.db.timestamps import utcnow
from app.overseas.auth.models import Member
from app.overseas.execution.models import Job
from app.overseas.execution.queue import enqueue
from app.overseas.management.models import Audit
from app.overseas.management.settings import freeze
from app.overseas.plans.snapshot import SKILL
from test_overseas_tasks import overseas, setup, create, payload, HEADERS, ROOT, add_member
from test_overseas_assignment import change_roles

MANAGE = ROOT + '/management'


def config(client, **updates):
    current = client.get(MANAGE + '/settings').json()
    current.pop('autoCleanup')
    return {**current, **updates}


def skill(client, stage='analysis', name='sample'):
    result = client.post(MANAGE + '/skills', json={'name': name, 'stage': stage,
        'files': {'SKILL.md': 'first'}}, headers=HEADERS)
    assert result.status_code == 201, result.text
    return result.json()


def test_skill_immutable_freeze_audit_conflict_and_disabled_default(overseas):
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    item = skill(client)
    body = config(client, timeoutSeconds=120, defaults={'analysis': item['id'], 'generation': None, 'revision': None})
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 200
    with factory.begin() as session:
        old = freeze(session, 'analysis', SKILL)
    published = client.post(MANAGE + '/skills/' + item['id'] + '/versions',
        json={'version': 1, 'files': {'SKILL.md': 'second'}}, headers=HEADERS)
    assert published.status_code == 200 and len(published.json()['versions']) == 2
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 409
    with factory.begin() as session:
        new = freeze(session, 'analysis', SKILL)
    assert old['skill']['version'] == 1 and old['skill']['files']['SKILL.md'] == 'first'
    assert new['skill']['version'] == 2 and new['runtime'] == {'timeoutSeconds': 120}
    patch = {'version': 2, 'enabled': False}
    assert client.patch(MANAGE + '/skills/' + item['id'], json=patch, headers=HEADERS).status_code == 200
    with factory.begin() as session, pytest.raises(Exception) as caught:
        freeze(session, 'analysis', SKILL)
    assert caught.value.status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Audit)) == 4
    assert client.patch(MANAGE + '/skills/' + item['id'], json=patch, headers=HEADERS).status_code == 409
    change_roles(factory, actor, ('operator',))
    assert client.get(MANAGE + '/skills').status_code == 403
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 403


@pytest.mark.parametrize('files', [ {'SKILL.md': 'x', '../escape': 'x'}, {'SKILL.md': 'x', '/abs': 'x'},
    {'SKILL.md': 'x', 'a\\b': 'x'}, {'SKILL.md': 'x', 'a/./b': 'x'}, {'SKILL.md': 'x', 'CON': 'x'},
    {'SKILL.md': 'x', 'a': 'x', 'a/b': 'x'}, {'SKILL.md': 'x', 'skill.md': 'x'}, {'other': 'x'},
    {'SKILL.md': ' '}, {'SKILL.md': 'x\x00'}, {'SKILL.md': 'x', 'a.': 'x'}])
def test_unsafe_skill_rejected_without_writes(overseas, files):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    result = client.post(MANAGE + '/skills', json={'name': 'sample', 'stage': 'analysis', 'files': files}, headers=HEADERS)
    assert result.status_code == 422
    assert client.get(MANAGE + '/skills').json() == {'items': []}


def test_settings_bounds_binding_csrf_and_secret_rejection(overseas):
    client, _, _, _ = setup(overseas, ('super_admin',))
    item = skill(client, stage='generation')
    body = config(client)
    for update in ({'concurrency': 6}, {'concurrency': 0}, {'timeoutSeconds': 9}, {'timeoutSeconds': 7201},
                   {'autoCleanup': True}, {'codexAuthFile': 'secret'}, {'concurrency': True},
                   {'defaults': {'analysis': item['id'], 'generation': None, 'revision': None}}):
        assert client.patch(MANAGE + '/settings', json={**body, **update}, headers=HEADERS).status_code == 422
    assert client.patch(MANAGE + '/settings', json=body).status_code == 403
    assert client.post(MANAGE + '/skills', json={'name': 'sample', 'stage': 'analysis',
        'files': {'SKILL.md': 'duplicate'}}, headers=HEADERS).status_code == 409
    assert client.get(MANAGE + '/settings').json()['version'] == 1


def test_scoped_stats_filters_pagination_and_unknown_tokens(overseas):
    client, factory, actor, designer = setup(overseas)
    task = create(client, payload(designer)).json()
    other = add_member(factory, ('operator',))
    with factory.begin() as session:
        from app.overseas.tasks.models import Task
        hidden = Task(name='secret', product_name='p', brand='b', platform='Amazon', market='US',
                      created_by=other, designer_id=other)
        session.add(hidden)
        session.flush()
        enqueue(session, hidden.id, 'analysis', 'secret', {'secret': 'do not expose'})
        for i in range(3):
            job = enqueue(session, task['id'], 'analysis', str(i), {'path': 'private'})
            job.created_at = utcnow() + timedelta(seconds=i)
            if i < 2:
                job.status, job.execution_count, job.error = 'failed', 1, 'private log'
                job.usage = {'input_tokens': 10, 'output_tokens': 20} if i == 0 else {'input_tokens': 5}
    response = client.get(MANAGE + '/jobs?pageSize=1&page=2&status=failed').json()
    assert response['total'] == 2 and len(response['items']) == 1
    assert 'private' not in str(response) and 'secret' not in str(response)
    counts = client.get(MANAGE + '/usage').json()
    assert counts['jobs'] == 3 and counts['queued'] == 1 and counts['failed'] == 2
    assert counts['inputTokens'] == 15 and counts['outputTokens'] is None and counts['cost'] is None
    assert client.get(MANAGE + '/usage?status=queued').json()['inputTokens'] is None
    assert client.get(MANAGE + '/jobs?kind=revision').json()['total'] == 0
    assert client.get(MANAGE + '/jobs?from=2026-01-02&to=2026-01-01').status_code == 422
    change_roles(factory, actor, ('designer',))
    assert client.get(MANAGE + '/jobs').json()['total'] == 0
    change_roles(factory, actor, ('design_manager',))
    assert client.get(MANAGE + '/jobs').json()['total'] == 4
    assert client.get(MANAGE + '/settings').status_code == 403
