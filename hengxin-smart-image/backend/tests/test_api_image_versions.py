from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

from sqlalchemy import select

from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.versions import execution_inputs, publish_result
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api, upload


def setup_result(client, factory, count=1):
    task_id, _ = create(client, count=count)
    with factory.begin() as session:
        task = session.get(ApiTask, UUID(task_id))
        for item in session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)):
            publish_result(session, item, task, item.source_id)
            item.state = 'succeeded'
        task.state = 'succeeded'
    item = client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    return task_id, item, f"{ROOT}/tasks/{task_id}/items/{item['id']}"


def post(client, path, data=None, key=None):
    return client.post(path, json=data, headers={'Idempotency-Key': key or str(uuid4())})


def test_revision_cas_frozen_inputs_retry_history_and_restore(files_env):
    client, factory, _, identity = files_env
    task_id, first, path = setup_result(client, factory)
    annotation = upload(client, 'annotation.png')
    with factory.begin() as session:
        editor = UserRecord(id=uuid4(), name='修改操作者', role='operator', status='active',
                            identity_source='development')
        session.add(editor)
        identity[0] = editor.id
    body = {'baseVersion': 1, 'text': '修改文字', 'annotationFileId': annotation['fileId']}
    assert post(client, path + '/revise', body, 'edit').status_code == 202
    assert post(client, path + '/revise', body, 'edit').status_code == 202
    assert post(client, path + '/revise', {**body, 'text': '不同'}, 'edit').status_code == 409
    assert post(client, path + '/restore', {'version': 1}).status_code == 409
    assert client.get(f'{ROOT}/tasks/{task_id}/zip').status_code == 409
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        records, prompt = execution_inputs(session, item, session.get(ApiTask, item.task_id))
        assert str(records[0].id) == first['result']['fileId']
        assert str(records[3].id) == annotation['fileId'] and '修改文字' in prompt
        item.state, item.error = 'failed', '上游失败'
        session.get(ApiTask, item.task_id).state = 'partial_failed'
    failed = client.get(f'{ROOT}/tasks/{task_id}').json()
    assert failed['operator'] == '测试操作者'
    assert failed['items'][0]['result'] == first['result']
    assert failed['items'][0]['revision']['operator'] == '修改操作者'
    assert post(client, path + '/restore', {'version': 1}).status_code == 409
    assert post(client, path + '/retry', key='retry').status_code == 202
    assert post(client, path + '/retry', key='retry').status_code == 202
    new = upload(client, 'new.png')
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        task = session.get(ApiTask, item.task_id)
        assert item.revision_source_id == UUID(first['result']['fileId'])
        publish_result(session, item, task, UUID(new['fileId']))
        item.state = task.state = 'succeeded'
    result = client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    assert [v['number'] for v in result['versions']] == [1, 2]
    assert result['versions'][1]['baseVersion'] == 1
    assert result['versions'][1]['operator'] == '修改操作者'
    assert post(client, path + '/revise', body).status_code == 409
    assert post(client, path + '/restore', {'version': 1}, 'restore').status_code == 200
    with factory() as session:
        assert session.get(ApiItem, UUID(first['id'])).revision_snapshot is None
    assert post(client, path + '/restore', {'version': 1}, 'restore').status_code == 200
    assert client.delete(ROOT + '/files/' + new['fileId']).status_code == 409
    assert client.delete(ROOT + '/files/' + annotation['fileId']).status_code == 409
    assert post(client, path + '/revise', {'baseVersion': 1, 'text': '再修改'}).status_code == 202
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        assert item.revision_snapshot['fileIds'][0] == first['result']['fileId']
        publish_result(session, item, session.get(ApiTask, item.task_id), UUID(new['fileId']))
        assert item.current_version == 3
    with factory() as session:
        assert len(session.scalars(select(ApiVersion)).all()) == 3


def test_legacy_result_compatibility_and_validation(files_env):
    client, factory, _, _ = files_env
    task_id, _ = create(client, count=1)
    with factory.begin() as session:
        item = session.scalar(select(ApiItem))
        item.result_id, item.state = item.source_id, 'succeeded'
        item_id = str(item.id)
        session.get(ApiTask, item.task_id).state = 'succeeded'
    path = f'{ROOT}/tasks/{task_id}/items/{item_id}'
    view = client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    assert view['currentVersion'] == view['versions'][0]['number'] == 1
    assert post(client, path + '/revise', {'baseVersion': 1, 'text': ' '}).status_code == 422
    assert post(client, path + '/revise', {'baseVersion': 1, 'annotationFileId': str(uuid4())}).status_code == 404
    assert post(client, path + '/restore', {'version': 9}).status_code == 404
    assert post(client, path + '/revise', {'baseVersion': 1, 'text': '修改'}).status_code == 202
    with factory() as session:
        assert len(session.scalars(select(ApiVersion)).all()) == 1
    other_id, _ = create(client, count=1)
    assert post(client, f'{ROOT}/tasks/{other_id}/items/{item_id}/retry').status_code == 404


def test_zip_success_snapshot_failure_retry_and_permission(files_env):
    client, factory, store, identity = files_env
    task_id, first, path = setup_result(client, factory, count=2)
    store.fail_open = True
    assert client.get(f'{ROOT}/tasks/{task_id}/zip').status_code == 503
    store.fail_open = False
    result = client.get(f'{ROOT}/tasks/{task_id}/zip')
    assert result.status_code == 200 and result.headers['content-type'] == 'application/zip'
    with ZipFile(BytesIO(result.content)) as archive:
        assert archive.namelist() == ['01.png', '02.png']
        assert all(archive.read(name) == image_bytes() for name in archive.namelist())
    assert all(stream.closed and stream.released for stream in store.streams)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert client.get(f'{ROOT}/tasks/{task_id}/zip').status_code == 403
    assert post(client, path + '/restore', {'version': 1}).status_code == 403


def test_batch_projection(files_env):
    client, factory, _, _ = files_env
    task_id, _ = create(client, count=11)
    assert client.get(f'{ROOT}/tasks/{task_id}').json()['batch'] == {'current': 1, 'total': 2, 'running': 0}
    with factory.begin() as session:
        items = session.scalars(select(ApiItem).order_by(ApiItem.position)).all()
        for item in items[:10]:
            item.state = 'succeeded'
        items[-1].state = 'running'
    assert client.get(f'{ROOT}/tasks/{task_id}').json()['batch'] == {'current': 2, 'total': 2, 'running': 1}


def test_zip_uses_selection_captured_before_object_reads(files_env, monkeypatch):
    client, factory, store, _ = files_env
    task_id, _, _ = setup_result(client, factory, count=2)
    new = upload(client, 'alternative.png')
    with factory() as session:
        items = session.scalars(select(ApiItem).order_by(ApiItem.position)).all()
        expected = [i.result_id for i in items]
        last_id = items[-1].id
    opened = []
    original_open = store.open
    def open_and_switch(record):
        opened.append(record.id)
        if len(opened) == 1:
            with factory.begin() as session:
                item = session.get(ApiItem, last_id)
                publish_result(session, item, session.get(ApiTask, item.task_id), UUID(new['fileId']))
        return original_open(record)
    monkeypatch.setattr(store, 'open', open_and_switch)
    assert client.get(f'{ROOT}/tasks/{task_id}/zip').status_code == 200
    assert opened == expected
