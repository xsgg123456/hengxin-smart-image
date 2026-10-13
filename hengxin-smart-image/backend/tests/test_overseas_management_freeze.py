from sqlalchemy import select
from app.overseas.execution import claims
from app.overseas.execution.models import Job
from test_overseas_materials import materials
from test_overseas_tasks import overseas, HEADERS
from test_overseas_assignment import change_roles
from test_overseas_plans import prepared, plans, publish, post
from test_overseas_pictures import generate, picture_list, action
from test_overseas_management import MANAGE, config
from overseas_installed_helpers import install_sample


def test_confirmation_uses_new_binding_retry_keeps_old_revision_uses_current(materials, monkeypatch, tmp_path):
    client, factory, actor, task = prepared(materials, monkeypatch)
    change_roles(factory, actor, ('super_admin',))
    generation = install_sample('new-generation')
    revision = install_sample('new-revision')
    body = config(client, timeoutSeconds=120, defaults={
        'analysis': None, 'generation': generation['id'], 'revision': revision['id']})
    assert client.patch(MANAGE + '/settings', json=body, headers=HEADERS).status_code == 200
    plan = plans(client, task)[0]
    publish(factory, plan)
    response = post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 3}, 'confirm')
    assert response.status_code == 200
    with factory.begin() as session:
        queued = session.scalars(select(Job).where(Job.kind == 'generation').order_by(Job.created_at)).all()
        first, second = queued
        assert all(j.payload['skill']['name'] == 'new-generation' for j in queued)
        assert all(j.payload['runtime'] == {'timeoutSeconds': 120} for j in queued)
        original = second.payload
        first_id, second_sku = first.id, second.payload['sku']['code']
        claims.end(session, second, 'failed', error=True)
    install_sample('new-generation', content='published after queue')
    assert client.patch(MANAGE + '/settings', json=config(client, timeoutSeconds=180), headers=HEADERS).status_code == 200
    retried = post(client, task, '/generation/retry', {'version': response.json()['version'], 'sku': second_sku}, 'retry')
    assert retried.status_code == 200
    with factory() as session:
        latest = session.scalar(select(Job).where(Job.kind == 'generation').order_by(Job.created_at.desc()))
        assert latest.payload == original
    from app.overseas.generation import delivery
    monkeypatch.setattr(delivery, 'get_store', lambda: materials[-1])
    generate(factory, first_id, tmp_path)
    listing = picture_list(client, task)
    revised = action(client, listing['items'][0], '/revisions', listing['taskVersion'], 'revision', note='change', marks=[])
    assert revised.status_code == 200, revised.text
    with factory() as session:
        job = session.scalar(select(Job).where(Job.kind == 'revision'))
        assert job.payload['skill']['name'] == 'new-revision'
        assert job.payload['runtime'] == {'timeoutSeconds': 180}
        revision_id = job.id
    generate(factory, revision_id, tmp_path, 'blue')
    usage = client.get(MANAGE + '/usage').json()
    assert usage['generationImages'] == 1 and usage['revisionImages'] == 1
    usage = client.get(MANAGE + '/usage?kind=revision').json()
    assert usage['generationImages'] == 0 and usage['revisionImages'] == 1
    monitor = client.get(MANAGE + '/jobs?kind=revision').json()
    assert monitor['total'] == 1 and monitor['items'][0]['imageCount'] == 1
