"""Real HTTP send/freeze and protocol binding; no paid model invocation."""
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from app.core.idempotency import fingerprint_payload
from app.overseas.execution.models import Job
from app.overseas.studio import execution
from app.overseas.studio.models import Picture
from app.overseas.tasks.models import TaskRequest
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish, output


@pytest.fixture
def editable(studio):
    client, factory, _, task, _, store = studio
    turn = send(client, task).json()['turns'][0]
    pictures = [output(store), output(store)]  # Both are named result.png.
    finish(factory, turn, pictures)
    response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
        files={'file': ('result.png', store.data[pictures[0]['object_key']])}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return studio, pictures, response.json()


def request(pictures, annotation):
    return dict(text='整体补充：保持比例', referencePictureIds=[p['id'] for p in pictures],
        attachmentIds=[annotation['id']], imageEdits=[
            dict(pictureId=pictures[0]['id'], annotationId=annotation['id'], text='1：改为蓝色'),
            dict(pictureId=pictures[1]['id'], annotationId=None, text='仅调整第二张背景')])


def test_freeze_readable_message_and_idempotent_retry(editable):
    (client, factory, _, task, _, _), pictures, annotation = editable
    body = request(pictures, annotation)
    result = send(client, task, key='edit', **body)
    assert result.status_code == 200, result.text
    turn = result.json()['turns'][-1]
    assert turn['text'] == '修改result.png：\n1：改为蓝色\n\n修改result.png：\n仅调整第二张背景\n\n整体补充：保持比例'
    assert len(turn['referencePictures']) == 2 and len(turn['attachments']) == 1
    assert send(client, task, key='edit', **body).json() == result.json()
    changed = json.loads(json.dumps(body))
    changed['imageEdits'][0]['text'] = '不同意见'
    assert send(client, task, key='edit', **changed).status_code == 409
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 2
        frozen = session.get(Job, UUID(turn['jobId'])).payload
        assert frozen['text'] == body['text']
        assert [row['id'] for row in frozen['inputs']] == [annotation['id'][7:], *body['referencePictureIds']]
        assert [e['pictureInputIndex'] for e in frozen['imageEdits']] == [1, 2]
        assert frozen['imageEdits'][0]['annotationInputIndex'] == 0
        assert frozen['imageEdits'][1]['annotationInputIndex'] is None


@pytest.mark.parametrize('failure', ['missing_reference', 'missing_attachment', 'duplicate_picture',
    'duplicate_annotation', 'no_opinion', 'annotation_no_description', 'invalid_annotation',
    'material_as_annotation', 'too_long', 'missing_picture', 'missing_upload', 'document'])
def test_reject_invalid_edits_without_creating_job(editable, failure):
    (client, factory, _, task, material, _), pictures, annotation = editable
    body = request(pictures, annotation)
    expected = 422
    if failure == 'missing_reference':
        body['referencePictureIds'] = []
    elif failure == 'missing_attachment':
        body['attachmentIds'] = []
    elif failure == 'duplicate_picture':
        body['imageEdits'][1]['pictureId'] = pictures[0]['id']
    elif failure == 'duplicate_annotation':
        body['imageEdits'][1]['annotationId'] = annotation['id']
    elif failure == 'no_opinion':
        body['text'] = ' '
        body['imageEdits'][1]['text'] = ' '
    elif failure == 'annotation_no_description':
        body['imageEdits'][0]['text'] = ' '
    elif failure in ('invalid_annotation', 'material_as_annotation', 'missing_upload', 'document'):
        identity = {'invalid_annotation': 'upload:bad', 'material_as_annotation': 'task:' + material['id'],
                    'missing_upload': 'upload:' + str(uuid4())}.get(failure)
        if failure == 'document':
            identity = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
                files={'file': ('notes.txt', b'hello')}, headers=HEADERS).json()['id']
        body['imageEdits'][0]['annotationId'] = identity
        body['attachmentIds'] = [identity]
        if failure == 'missing_upload':
            expected = 404
    elif failure == 'too_long':
        body['imageEdits'][0]['text'] = '字' * 4001
    elif failure == 'missing_picture':
        body['imageEdits'][0]['pictureId'] = body['referencePictureIds'][0] = str(uuid4())
        expected = 404
    response = send(client, task, key='invalid', **body)
    assert response.status_code == expected, response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


@pytest.mark.parametrize('target', ['picture', 'annotation'])
def test_cross_task_binding_rejected(editable, target):
    from app.overseas.studio.models import Upload
    from app.overseas.tasks.models import Task
    (client, factory, _, task, _, _), pictures, annotation = editable
    with factory.begin() as session:
        source = session.get(Task, UUID(task['id']))
        other = Task(name='other', product_name='phone', brand='brand', platform='Amazon',
            market='US', created_by=source.created_by, designer_id=source.designer_id)
        session.add(other)
        session.flush()
        model, identity = (Picture, pictures[0]['id']) if target == 'picture' else (Upload, annotation['id'][7:])
        session.get(model, UUID(identity)).task_id = other.id
    assert send(client, task, key='cross', **request(pictures, annotation)).status_code == 404


def test_original_only_edit_accepts_main_text(editable):
    (client, _, _, task, _, _), pictures, _ = editable
    response = send(client, task, key='original', text='改成蓝色', referencePictureIds=[pictures[0]['id']],
        imageEdits=[dict(pictureId=pictures[0]['id'])])
    assert response.status_code == 200, response.text


def test_old_fingerprint_and_empty_edits_replay_unchanged(studio):
    client, factory, _, task, _, _ = studio
    result = send(client, task)
    legacy = dict(text='设计产品', skillId=None, attachmentIds=[], referencePictureIds=[])
    with factory() as session:
        record = session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send'))
        assert record.body_hash == fingerprint_payload(legacy)
    assert send(client, task, imageEdits=[]).json() == result.json()


def test_registered_paths_same_names_long_text_and_frozen_indices(editable, tmp_path):
    from app.overseas.studio.context_assets import register
    (client, factory, _, task, _, store), pictures, annotation = editable
    body = request(pictures, annotation)
    body['text'] = '整体补充' * 2000
    body['imageEdits'][0]['text'] = '编号1修改完整说明' * 400
    response = send(client, task, key='long', **body)
    assert response.status_code == 200, response.text
    with factory() as session:
        frozen = session.get(Job, UUID(response.json()['turns'][-1]['jobId'])).payload
    # Use the same registered persistent paths as the workspace preparation.
    _, paths = register(dict(assets={}, aliases={}, managed_turns=[]), [], frozen['inputs'], 'turn', tmp_path)
    workspace = SimpleNamespace(input_paths=paths, previous_session='same-session')
    prompt = execution.HANDLER.prepare(SimpleNamespace(payload=frozen), workspace)
    data = json.loads(prompt.split('图片修改要求：', 1)[1].split('\n', 1)[1].split('\n\n附件文件：')[0])
    assert data[0]['originalPath'] == paths[1]['path']
    assert data[0]['annotationPath'] == paths[0]['path']
    assert data[1]['originalPath'] == paths[2]['path']
    assert len({data[0]['originalPath'], data[1]['originalPath'], data[0]['annotationPath']}) == 3
    assert body['text'] in prompt and body['imageEdits'][0]['text'] in prompt
    assert '原图为编辑基础' in prompt and '不得画进成品' in prompt
    frozen['imageEdits'][0]['pictureInputIndex'] = 0
    with pytest.raises(ValueError, match='frozen input mismatch'):
        execution.HANDLER.prepare(SimpleNamespace(payload=frozen), workspace)


def test_standalone_prompt_reads_frozen_original_and_annotation_bytes(editable, tmp_path, monkeypatch):
    (client, factory, _, task, _, store), pictures, annotation = editable
    response = send(client, task, key='files', **request(pictures, annotation))
    with factory() as session:
        frozen = session.get(Job, UUID(response.json()['turns'][-1]['jobId'])).payload
    monkeypatch.setattr(execution, 'get_store', lambda: store)
    workspace = SimpleNamespace(work=tmp_path, previous_session='same-session')
    prompt = execution.HANDLER.prepare(SimpleNamespace(payload=frozen), workspace)
    for index, source in enumerate(frozen['inputs'], 1):
        assert (tmp_path / 'inputs' / f'{index}.png').read_bytes() == store.data[source['object_key']]
    data = json.loads(prompt.split('图片修改要求：', 1)[1].split('\n', 1)[1].split('\n\n附件文件：')[0])
    assert data[0]['annotationPath'] == '/work/inputs/1.png'
    assert data[0]['originalPath'] == '/work/inputs/2.png'
    assert data[1]['originalPath'] == '/work/inputs/3.png'


@pytest.mark.parametrize('target', ['picture', 'annotation'])
def test_unsupported_source_image_type_rejected(editable, target):
    from app.overseas.studio.models import Upload
    (client, factory, _, task, _, _), pictures, annotation = editable
    with factory.begin() as session:
        model, identity = (Picture, pictures[0]['id']) if target == 'picture' else (Upload, annotation['id'][7:])
        session.get(model, UUID(identity)).content_type = 'image/svg+xml' if target == 'picture' else 'image/jpeg'
    assert send(client, task, key='type', **request(pictures, annotation)).status_code == 422


def test_legacy_payload_without_edits_preserves_prompt():
    workspace = SimpleNamespace(input_paths=[], previous_session='same-session')
    assert execution.HANDLER.prepare(SimpleNamespace(payload=dict(text='原始文字', inputs=[])), workspace) == '原始文字'
