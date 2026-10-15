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


def test_installed_freeze_and_settings_audit(overseas):
    from overseas_installed_helpers import install_sample
    from app.overseas.management.installed_catalog import frozen_package
    client, factory, actor, _ = setup(overseas, ('super_admin',))
    item = install_sample()
    body = config(client, timeoutSeconds=120, defaults={'analysis': item['id'], 'generation': None, 'revision': None})
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 200
    with factory.begin() as session:
        old = freeze(session, 'analysis', SKILL)
    install_sample(content='second')
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 409
    with factory.begin() as session:
        new = freeze(session, 'analysis', SKILL)
    assert frozen_package(old['skill']).files['SKILL.md'].endswith(b'first')
    assert frozen_package(new['skill']).files['SKILL.md'].endswith(b'second')
    assert old['skill']['installedRelease'] != new['skill']['installedRelease']
    assert new['runtime'] == {'timeoutSeconds': 120}
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Audit)) == 1
    change_roles(factory, actor, ('operator',))
    assert client.get(MANAGE + '/skills').status_code == 403
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 403


def test_skill_browser_writes_are_removed(overseas):
    client, factory, _, _ = setup(overseas, ('super_admin',))
    from uuid import uuid4
    for method, path in [('POST', '/skills'), ('POST', '/skills/' + str(uuid4()) + '/versions'),
                         ('PATCH', '/skills/' + str(uuid4())), ('POST', '/skill-packages')]:
        response = client.request(method, MANAGE + path, json={'files': {'SKILL.md': 'x'}}, headers=HEADERS)
        assert response.status_code in (404, 405)
    assert client.get(MANAGE + '/skills').json() == {'items': []}


def test_settings_bounds_binding_csrf_and_secret_rejection(overseas):
    from uuid import uuid4
    client, _, _, _ = setup(overseas, ('super_admin',))
    body = config(client)
    for update in ({'concurrency': 6}, {'concurrency': 0}, {'timeoutSeconds': 9}, {'timeoutSeconds': 7201},
                   {'autoCleanup': True}, {'codexAuthFile': 'secret'}, {'concurrency': True},
                   {'defaults': {'analysis': str(uuid4()), 'generation': None, 'revision': None}}):
        assert client.patch(MANAGE + '/settings', json={**body, **update}, headers=HEADERS).status_code == 422
    assert client.patch(MANAGE + '/settings', json=body).status_code == 403
    assert client.get(MANAGE + '/settings').json()['version'] == 1


def test_scoped_stats_filters_pagination_without_usage(overseas):
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
    response = client.get(MANAGE + '/jobs?pageSize=1&page=2&status=failed').json()
    assert response['total'] == 2 and len(response['items']) == 1
    assert 'private' not in str(response) and 'secret' not in str(response)
    counts = client.get(MANAGE + '/usage').json()
    assert counts['jobs'] == 3 and counts['queued'] == 1 and counts['failed'] == 2
    assert not {'inputTokens', 'outputTokens', 'cost'} & counts.keys()
    assert not {'inputTokens', 'outputTokens', 'cost'} & response['items'][0].keys()
    assert response['items'][0]['operatorId'] is None
    assert client.get(MANAGE + '/jobs?kind=revision').json()['total'] == 0
    assert client.get(MANAGE + '/jobs?from=2026-01-02&to=2026-01-01').status_code == 422
    change_roles(factory, actor, ('designer',))
    assert client.get(MANAGE + '/jobs').json()['total'] == 0
    change_roles(factory, actor, ('design_manager',))
    assert client.get(MANAGE + '/jobs').json()['total'] == 4
    assert client.get(MANAGE + '/settings').status_code == 403
