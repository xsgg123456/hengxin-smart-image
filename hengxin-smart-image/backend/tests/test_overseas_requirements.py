"""Human review gate, authorization, replay, revisions and immutable evidence."""
from uuid import UUID
import pytest
from sqlalchemy import func, select
from app.overseas.auth.models import Member
from app.overseas.execution.models import Job, JobOutbox
from app.overseas.materials.models import Material
from app.overseas.plans.models import Plan
from app.overseas.tasks.models import RequirementsReview, Task
from test_overseas_tasks import overseas, create, payload, add_member, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_assignment import change_roles
from test_overseas_plans import post


def pending(materials):
    client, factory, actor, designer, _ = materials
    data = upload(client).json()
    response = create(client, {**payload(designer), 'materialIds': [data['id']]})
    assert response.status_code == 201, response.text
    return response.json(), data


def review(client, task, decision='approve', comment='', key='review'):
    return post(client, task, '/requirements-review',
                {'version': task['version'], 'decision': decision, 'comment': comment}, key)


def test_pending_blocks_ai_and_approve_enqueues_once(materials):
    client, factory, actor, _, _ = materials
    task, material = pending(materials)
    assert task['status'] == 'pending_review' and task['requirementsReviews'] == []
    assert 'task.requirements.review' not in task['capabilities']
    change_roles(factory, actor, ('operator', 'design_manager'))
    current = client.get(ROOT + '/tasks/' + task['id']).json()
    assert 'task.requirements.review' in current['capabilities']
    assert post(client, task, '/analysis', {'version': 1}).status_code == 409
    with factory() as session:
        for model in (Job, JobOutbox, Plan):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    approved = review(client, task)
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result['status'] == 'analyzing' and result['version'] == 2
    assert 'task.requirements.review' not in result['capabilities']
    item = result['requirementsReviews'][0]
    assert item['decision'] == 'approve' and item['actorId'] == str(actor) and item['version'] == 1
    assert item['materialIds'] == [material['id']]
    assert review(client, task).json() == result
    assert review(client, task, comment='different').status_code == 409
    assert review(client, result, key='duplicate').status_code == 409
    with factory() as session:
        for model in (Job, JobOutbox, Plan, RequirementsReview):
            assert session.scalar(select(func.count()).select_from(model)) == 1


@pytest.mark.parametrize('roles', [('operator',), ('super_admin',), ('designer',)])
def test_review_requires_design_scope(materials, roles):
    client, factory, actor, _, _ = materials
    task, _ = pending(materials)
    change_roles(factory, actor, roles)
    assert review(client, task).status_code == 403


def test_reject_resubmit_replace_and_preserve_evidence(materials):
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    change_roles(factory, actor, ('operator', 'design_manager'))
    assert review(client, task, 'reject', '   ').status_code == 422
    stale = {**task, 'version': 2}
    assert review(client, stale, 'reject', '补全').status_code == 409
    rejected = review(client, task, 'reject', '补全SKU').json()
    assert rejected['status'] == 'returned'
    assert 'task.requirements.resubmit' in rejected['capabilities']
    assert post(client, task, '/analysis', {'version': 2}).status_code == 409
    newer = upload(client, b'name,value\nnew,99\n').json()
    body = {**payload(designer), 'name': '修订商品', 'skus': [{'code': 'NEW'}],
            'version': 2, 'materialIds': [newer['id']]}
    response = post(client, task, '/resubmit', body, 'resubmit')
    assert response.status_code == 200, response.text
    resubmitted = response.json()
    assert resubmitted['status'] == 'pending_review' and resubmitted['version'] == 3
    assert resubmitted['skus'] == [{'code': 'NEW'}]
    assert resubmitted['requirementsReviews'][0]['materialIds'] == [original['id']]
    assert resubmitted['requirementsReviews'][0]['submission']['skus'] == [{'code': 'A'}, {'code': 'B'}]
    assert post(client, task, '/resubmit', body, 'resubmit').json() == resubmitted
    assert post(client, task, '/resubmit', {**body, 'remarks': '不同'}, 'resubmit').status_code == 409
    assert post(client, task, '/resubmit', {**body, 'version': 3}, 'duplicate').status_code == 409
    current = client.get(ROOT + '/tasks/' + task['id'] + '/materials').json()
    assert [item['id'] for item in current] == [newer['id']]
    path = ROOT + '/materials/' + original['id']
    assert client.get(path + '/content').content == b'name,value\nitem,42\n'
    assert client.delete(path, headers=HEADERS).status_code == 409
    approved = review(client, resubmitted, key='review-v3')
    assert approved.status_code == 200, approved.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Material)) == 2
        frozen = session.scalar(select(Job)).payload
        assert [item['id'] for item in frozen['materials']] == [newer['id']]
        assert frozen['task']['skus'] == [{'code': 'NEW'}]
    change_roles(factory, actor, ('designer',))
    assert client.get(path + '/content').status_code == 403


def test_resubmit_authority_and_retained_materials(materials):
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    change_roles(factory, actor, ('operator', 'design_manager'))
    returned = review(client, task, 'reject', '补充').json()
    body = {**payload(designer), 'version': returned['version'], 'materialIds': [original['id']]}
    for roles in (('designer',), ('super_admin',)):
        change_roles(factory, actor, roles)
        assert post(client, task, '/resubmit', body).status_code == 403
    other = add_member(factory, ('operator',))
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).created_by = other
    change_roles(factory, actor, ('operator',))
    assert post(client, task, '/resubmit', body).status_code == 403
    change_roles(factory, actor, ('operator_manager',))
    assert post(client, task, '/resubmit', {**body, 'designerId': str(actor)}).status_code == 422
    assert post(client, task, '/resubmit', body).status_code == 200


def test_resubmit_rejects_foreign_and_failed_materials_atomically(materials):
    client, factory, actor, designer, _ = materials
    task, original = pending(materials)
    failed = upload(client, b'%PDF-invalid', 'bad.pdf', 'requirement').json()
    foreign = upload(client).json()
    second = create(client, {**payload(designer), 'materialIds': [foreign['id']]}, 'second').json()
    change_roles(factory, actor, ('operator', 'design_manager'))
    review(client, task, 'reject', '补充')
    body = {**payload(designer), 'version': 2, 'name': '不能写入', 'materialIds': [failed['id']]}
    assert post(client, task, '/resubmit', body).status_code == 422
    assert post(client, task, '/resubmit', {**body, 'materialIds': [foreign['id']]}).status_code == 409
    assert post(client, task, '/resubmit', {**body, 'materialIds': []}).status_code == 422
    assert post(client, task, '/resubmit', {**body, 'materialIds': [original['id']], 'version': 1}).status_code == 409
    result = client.get(ROOT + '/tasks/' + task['id']).json()
    assert result['name'] == task['name'] and result['version'] == 2 and result['status'] == 'returned'


def test_assigned_designer_can_review_and_marker_blocks_direct_analysis(materials):
    from fastapi import HTTPException
    from app.overseas.plans.service import enqueue_analysis
    client, factory, actor, _, _ = materials
    task, _ = pending(materials)
    with factory.begin() as session:
        current = session.get(Task, UUID(task['id']))
        current.designer_id = actor
        # Even an accidentally altered status cannot bypass approval evidence.
        current.status = 'submitted'
        with pytest.raises(HTTPException, match='设计审核'):
            enqueue_analysis(session, current)
        current.status = 'pending_review'
    change_roles(factory, actor, ('designer',))
    assert review(client, task).status_code == 200


def test_resubmit_keep_one_replace_other_and_assignment_permission(materials, monkeypatch):
    from app.overseas.materials import parsers
    client, factory, actor, designer, _ = materials
    monkeypatch.setattr(parsers, 'parse_document', lambda *_: '完整资料文字')
    requirement = upload(client, b'%PDF-test', 'requirements.pdf', 'requirement').json()
    competitor = upload(client).json()
    task = create(client, {**payload(designer), 'materialIds': [requirement['id'], competitor['id']]}).json()
    change_roles(factory, actor, ('operator', 'design_manager'))
    review(client, task, 'reject', '替换竞品')
    replacement = upload(client).json()
    another_designer = add_member(factory)
    body = {**payload(designer), 'version': 2, 'materialIds': [requirement['id'], replacement['id']]}
    change_roles(factory, actor, ('operator',))
    assert post(client, task, '/resubmit', {**body, 'designerId': str(another_designer)}).status_code == 403
    change_roles(factory, actor, ('operator', 'design_manager'))
    response = post(client, task, '/resubmit', {**body, 'designerId': str(another_designer)})
    assert response.status_code == 200, response.text
    event = response.json()['events'][-1]
    assert event['beforeDesignerId'] == str(designer) and event['afterDesignerId'] == str(another_designer)
    current = client.get(ROOT + '/tasks/' + task['id'] + '/materials').json()
    assert {item['id'] for item in current} == {requirement['id'], replacement['id']}
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Material).where(Material.task_id == UUID(task['id']))) == 3
