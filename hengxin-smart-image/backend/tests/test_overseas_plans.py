"""Version/permission/transaction contracts with real API and isolated storage."""
from uuid import UUID
import pytest
from sqlalchemy import func, select
from app.overseas.auth.models import Member
from app.overseas.execution import claims, queue
from app.overseas.execution.models import Job, JobOutbox
from app.overseas.plans.analysis import HANDLER
from app.overseas.plans.models import Plan
from app.overseas.plans import snapshot
from app.overseas.tasks.models import Task
from test_overseas_materials import materials, upload, submit
from test_overseas_tasks import overseas, create, payload, ROOT, HEADERS
from test_overseas_assignment import change_roles

CONTENT = {'skus': [{'code': code, 'pictures': [{'title': '产品', 'description': '完整卖点',
    'prompt': 'Product photograph', 'width': 1024, 'height': 1024}]} for code in ('A', 'B')]}


def prepared(materials, monkeypatch):
    from app.overseas.materials import parsers
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: 'FULL DATA ' * 20000)
    client, factory, actor, designer, _ = materials
    material = upload(client).json()['id']
    task = create(client, {**payload(designer), 'materialIds': [material]}).json()
    change_roles(factory, actor, ('operator', 'design_manager'))
    return client, factory, actor, task


def plans(client, task):
    return client.get(ROOT + '/tasks/' + task['id'] + '/plans').json()['items']


def post(client, task, suffix, body, key='action'):
    return client.post(ROOT + '/tasks/' + task['id'] + suffix, json=body,
                       headers={**HEADERS, 'Idempotency-Key': key})


def publish(factory, plan):
    identity = UUID(plan['jobId'])
    token = claims.claim(factory, identity)
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    assert claims.finish(factory, identity, token, 'succeeded', CONTENT, publish=HANDLER.publish)


def test_automatic_freeze_confirm_replay_and_all_skus(materials, monkeypatch):
    client, factory, _, task = prepared(materials, monkeypatch)
    assert task['status'] == 'analyzing' and task['version'] == 1
    plan = plans(client, task)[0]
    assert plan['status'] == 'pending' and plan['content'] is None
    with factory() as session:
        frozen = session.get(Job, UUID(plan['jobId'])).payload
        assert frozen['materials'][0]['text'] == 'FULL DATA ' * 20000
        assert len(frozen['materials'][0]['checksum']) == 64
        assert frozen['skill']['files']['SKILL.md'] == snapshot.SKILL['files']['SKILL.md']
    assert post(client, task, '/analysis', {'version': 1}).status_code == 409
    assert post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 1}).status_code == 409
    publish(factory, plan)
    assert plans(client, task)[0]['content'] == CONTENT
    suffix = '/plans/' + plan['id'] + '/confirm'
    assert post(client, task, suffix, {'version': 1}).status_code == 409
    response = post(client, task, suffix, {'version': 2}, 'confirm')
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'generating' and response.json()['version'] == 3
    assert post(client, task, suffix, {'version': 2}, 'confirm').json() == response.json()
    assert post(client, task, suffix, {'version': 3}, 'duplicate').status_code == 409
    with factory() as session:
        jobs = session.scalars(select(Job).where(Job.kind == 'generation')).all()
        assert len(jobs) == 2 and len({j.payload['sku']['code'] for j in jobs}) == 2
        assert all(j.payload['plan'] == CONTENT and j.payload['materials'] == frozen['materials'] for j in jobs)
        assert all(j.payload['skill']['name'] == 'overseas-generation' for j in jobs)


def test_reanalysis_feedback_history_stale_and_failed_retry(materials, monkeypatch):
    client, factory, _, task = prepared(materials, monkeypatch)
    original = plans(client, task)[0]
    publish(factory, original)
    assert post(client, task, '/analysis', {'version': 2, 'feedback': '  '}).status_code == 422
    response = post(client, task, '/analysis', {'version': 2, 'feedback': '增加细节'}, 'modify')
    assert response.status_code == 200 and response.json()['version'] == 3
    history = plans(client, task)
    assert [p['status'] for p in history] == ['pending', 'ready']
    assert post(client, task, '/plans/' + original['id'] + '/confirm', {'version': 3}).status_code == 409
    with factory.begin() as session:
        job = claims.locked_job(session, UUID(history[0]['jobId']))
        claims.end(session, job, 'failed', error=True)
    assert plans(client, task)[0]['status'] == 'failed'
    assert client.get(ROOT + '/tasks/' + task['id']).json()['status'] == 'analysisFailed'
    assert client.get(ROOT + '/tasks?status=analysisFailed').json()['total'] == 1
    assert client.get(ROOT + '/tasks?status=analyzing').json()['total'] == 0
    assert post(client, task, '/analysis', {'version': 3}, 'retry').status_code == 200
    assert len(plans(client, task)) == 3


@pytest.mark.parametrize('roles', [('operator',), ('super_admin',), ('designer',)])
def test_business_roles_not_admin_and_not_unassigned_designer(materials, monkeypatch, roles):
    client, factory, actor, task = prepared(materials, monkeypatch)
    plan = plans(client, task)[0]
    publish(factory, plan)
    change_roles(factory, actor, roles)
    assert post(client, task, '/analysis', {'version': 2, 'feedback': 'change'}).status_code == 403
    assert post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 2}).status_code == 403


def test_uncertain_not_retryable_and_cancelled_retryable(materials, monkeypatch):
    client, factory, _, task = prepared(materials, monkeypatch)
    plan = plans(client, task)[0]
    with factory.begin() as session:
        job = session.get(Job, UUID(plan['jobId']))
        job.status = 'uncertain'
    assert plans(client, task)[0]['status'] == 'uncertain'
    assert post(client, task, '/analysis', {'version': 1}).status_code == 409
    with factory.begin() as session:
        claims.end(session, claims.locked_job(session, UUID(plan['jobId'])), 'cancelled')
    assert post(client, task, '/analysis', {'version': 1}, 'retry').status_code == 200


def test_enqueue_failure_rolls_back_submission(materials, monkeypatch):
    from app.overseas.materials import parsers
    from app.overseas.plans import service
    client, factory, _, designer, _ = materials
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: 'parsed')
    material = upload(client).json()['id']
    def fail(*args, **kwargs):
        queue.enqueue(*args, **kwargs)
        raise RuntimeError('atomic fault')
    monkeypatch.setattr(service, 'enqueue', fail)
    with pytest.raises(RuntimeError, match='atomic fault'):
        create(client, {**payload(designer), 'materialIds': [material]})
    with factory() as session:
        for model in (Task, Job, JobOutbox, Plan):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_legacy_submitted_task_can_start_and_missing_materials_rejected(materials, monkeypatch):
    from app.overseas.materials import parsers
    from app.overseas.materials.models import Material
    client, factory, actor, designer, _ = materials
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: 'legacy full text')
    material = upload(client).json()['id']
    task = create(client, payload(designer)).json()
    change_roles(factory, actor, ('operator', 'design_manager'))
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).status = 'submitted'
    assert post(client, task, '/analysis', {'version': 1}).status_code == 422
    with factory.begin() as session:
        session.get(Material, UUID(material)).task_id = UUID(task['id'])
    response = post(client, task, '/analysis', {'version': 1})
    assert response.status_code == 200 and response.json()['status'] == 'analyzing'
    assert len(plans(client, task)) == 1


def test_assigned_designer_can_confirm_and_publication_failure_atomic(materials, monkeypatch):
    client, factory, actor, task = prepared(materials, monkeypatch)
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).designer_id = actor
    change_roles(factory, actor, ('designer',))
    plan = plans(client, task)[0]
    identity = UUID(plan['jobId'])
    token = claims.claim(factory, identity)
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    def broken(session, job, result):
        HANDLER.publish(session, job, result)
        session.flush()
        raise RuntimeError('publish fault')
    with pytest.raises(RuntimeError, match='publish fault'):
        claims.finish(factory, identity, token, 'succeeded', CONTENT, publish=broken)
    with factory() as session:
        assert session.get(Plan, UUID(plan['id'])).status == 'pending'
        assert session.get(Task, UUID(task['id'])).version == 1
        assert session.get(Job, identity).status == 'running'
    assert claims.finish(factory, identity, token, 'succeeded', CONTENT, publish=HANDLER.publish)
    assert post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 2}).status_code == 200
