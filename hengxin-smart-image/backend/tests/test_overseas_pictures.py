"""Image lifecycle through real authenticated HTTP and fenced artifact publication."""
import json
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID
from zipfile import ZipFile
import pytest
from PIL import Image
from sqlalchemy import select
from app.overseas.execution import claims
from app.overseas.execution.models import Job
from app.overseas.generation import delivery
from app.overseas.pictures.models import PictureVersion
from test_overseas_plans import prepared, plans, publish, post
from test_overseas_materials import materials
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_assignment import change_roles


def png(size=(1024, 1024), color='red'):
    out = BytesIO()
    Image.new('RGB', size, color).save(out, 'PNG')
    return out.getvalue()


def confirmed(materials, monkeypatch):
    client, factory, actor, task = prepared(materials, monkeypatch)
    plan = plans(client, task)[0]
    publish(factory, plan)
    response = post(client, task, '/plans/' + plan['id'] + '/confirm', {'version': 3}, 'confirm')
    assert response.status_code == 200, response.text
    monkeypatch.setattr(delivery, 'get_store', lambda: materials[-1])
    return client, factory, actor, response.json()


def picture_list(client, task):
    return client.get(ROOT + '/tasks/' + task['id'] + '/pictures').json()


def action(client, picture, suffix, task_version, key, **extra):
    return client.post(ROOT + '/pictures/' + picture['id'] + suffix,
        json={'version': picture['version'], 'taskVersion': task_version, **extra},
        headers={**HEADERS, 'Idempotency-Key': key})


def generate(factory, job_id, tmp_path, color='red'):
    token = claims.claim(factory, job_id)
    assert token
    with factory() as session:
        job = session.get(Job, job_id)
        session.expunge(job)
    work = tmp_path / str(job_id)
    work.mkdir()
    position = job.payload.get('position', 0)
    (work / 'out.png').write_bytes(png(color=color))
    (work / 'outputs.json').write_text(json.dumps({'images': [{'position': position, 'path': 'out.png'}]}))
    result = delivery.HANDLER.validate(job, SimpleNamespace(work=work),
                                      SimpleNamespace(error=None, turn_completed=True, session_id='session'))
    with factory.begin() as session:
        session.get(Job, job_id).process_exited = True
    assert claims.finish(factory, job_id, token, 'succeeded', result, publish=delivery.HANDLER.publish)
    return result


def jobs(factory, kind='generation'):
    with factory() as session:
        return session.scalars(select(Job.id).where(Job.kind == kind).order_by(Job.created_at)).all()


def test_partial_retry_revision_history_review_archive(materials, monkeypatch, tmp_path):
    client, factory, actor, task = confirmed(materials, monkeypatch)
    assert all(p['version'] == 0 and p['url'] is None for p in picture_list(client, task)['items'])
    first, second = jobs(factory)
    generate(factory, first, tmp_path)
    with factory.begin() as session:
        claims.end(session, claims.locked_job(session, second), 'failed', error=True)
    listing = picture_list(client, task)
    assert [p['status'] for p in listing['items']] == ['ready', 'failed']
    assert post(client, task, '/generation/retry', {'version': listing['taskVersion'], 'sku': 'A'}, 'bad').status_code == 409
    result = post(client, task, '/generation/retry', {'version': listing['taskVersion'], 'sku': 'B'}, 'retry')
    assert result.status_code == 200, result.text
    assert post(client, task, '/generation/retry', {'version': listing['taskVersion'], 'sku': 'B'}, 'retry').status_code == 200
    generate(factory, jobs(factory)[-1], tmp_path)
    listing = picture_list(client, task)
    a, b = listing['items']
    approved = action(client, a, '/approve', listing['taskVersion'], 'approve-a')
    assert approved.status_code == 200
    version = approved.json()['version']
    revision = action(client, b, '/revisions', version, 'revise-b', note='蓝色背景', marks=[])
    assert revision.status_code == 200, revision.text
    assert action(client, b, '/revisions', version, 'revise-b', note='蓝色背景', marks=[]).status_code == 200
    assert action(client, b, '/revisions', revision.json()['version'], 'duplicate', note='x', marks=[]).status_code == 409
    generate(factory, jobs(factory, 'revision')[-1], tmp_path, 'blue')
    listing = picture_list(client, task)
    a, b = listing['items']
    assert a['approved'] and a['version'] == 1 and not b['approved'] and b['version'] == 2
    assert len(b['history']) == 2
    assert client.get(b['history'][1]['url']).content == png()
    assert post(client, task, '/archive', {'version': listing['taskVersion']}, 'early').status_code == 409
    approved = action(client, b, '/approve', listing['taskVersion'], 'approve-b').json()
    archived = post(client, task, '/archive', {'version': approved['version']}, 'archive')
    assert archived.status_code == 200 and archived.json()['status'] == 'archived'
    assert action(client, b, '/revisions', archived.json()['version'], 'after', note='x', marks=[]).status_code == 409
    archives = client.get(ROOT + '/archives?sku=B&product=手机&brand=品牌').json()
    assert archives['total'] == 1
    zip_response = client.get(ROOT + '/archives/' + archives['items'][0]['id'] + '/download')
    with ZipFile(BytesIO(zip_response.content)) as zipped:
        assert len(zipped.namelist()) == 2
        assert [zipped.read(name) for name in zipped.namelist()] == [png(), png(color='blue')]
    with factory() as session:
        stored = session.scalar(select(PictureVersion).where(PictureVersion.version == 2))
        object_key = stored.object_key
    materials[-1].data[object_key] = b'corrupted archived object'
    assert client.get(ROOT + '/archives/' + archives['items'][0]['id'] + '/download').status_code == 503
    materials[-1].data.pop(object_key)
    assert client.get(ROOT + '/archives/' + archives['items'][0]['id'] + '/download').status_code == 503
    change_roles(factory, actor, ('designer',))
    assert client.get(b['url']).status_code == 403
    assert client.get(ROOT + '/archives/' + archives['items'][0]['id'] + '/download').status_code == 403
    assert client.get(ROOT + '/archives').json()['total'] == 0


def test_revision_failure_keeps_original_and_can_retry(materials, monkeypatch, tmp_path):
    client, factory, _, task = confirmed(materials, monkeypatch)
    generate(factory, jobs(factory)[0], tmp_path)
    listing = picture_list(client, task)
    a = listing['items'][0]
    result = action(client, a, '/revisions', listing['taskVersion'], 'revision', note='修改', marks=[])
    assert result.status_code == 200
    job_id = jobs(factory, 'revision')[0]
    with factory.begin() as session:
        session.get(Job, job_id).status = 'uncertain'
    assert action(client, a, '/revisions', result.json()['version'], 'retry', note='修改', marks=[]).status_code == 409
    with factory.begin() as session:
        claims.end(session, claims.locked_job(session, job_id), 'failed', error=True)
    assert client.get(a['url']).content == png()
    assert picture_list(client, task)['items'][0]['status'] == 'failed'
    assert action(client, a, '/approve', result.json()['version'], 'approve-failed').status_code == 409
    assert action(client, a, '/revisions', result.json()['version'], 'retry', note='修改', marks=[]).status_code == 200


def test_marks_roles_stale_versions_and_storage_integrity(materials, monkeypatch, tmp_path):
    client, factory, actor, task = confirmed(materials, monkeypatch)
    generate(factory, jobs(factory)[0], tmp_path)
    listing = picture_list(client, task)
    a, version = listing['items'][0], listing['taskVersion']
    mark = dict(id='1', kind='rect', x=1020, y=0, width=10, height=10, points=[], note='change')
    assert action(client, a, '/revisions', version, 'bounds', note='', marks=[mark]).status_code == 422
    assert action(client, a, '/revisions', version, 'empty', note=' ', marks=[]).status_code == 422
    assert action(client, a, '/approve', version - 1, 'stale').status_code == 409
    change_roles(factory, actor, ('super_admin',))
    assert action(client, a, '/approve', version, 'admin').status_code == 403
    change_roles(factory, actor, ('design_manager',))
    with factory() as session:
        record = session.scalar(select(PictureVersion))
        key = record.object_key
    materials[-1].data[key] = b'broken'
    assert client.get(a['url']).status_code == 503
    materials[-1].data.pop(key)
    assert client.get(a['url']).status_code == 503
