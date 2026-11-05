"""Reference validation must reject atomically through the real send route."""
import copy
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import select, func
from app.overseas.execution.models import Job
from app.overseas.studio.models import Upload, Conversation
from app.overseas.studio.image_edits import freeze_edits
from app.overseas.studio.schemas import Send
from app.overseas.tasks.models import Task
from fastapi import HTTPException
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials
from test_overseas_studio import studio, send
from test_studio_image_edits import editable
from test_studio_image_references import referenced


@pytest.mark.parametrize('failure', ['missing_attachment', 'invalid_id', 'material', 'duplicate',
    'uuid_alias_duplicate', 'annotation', 'unknown_kind', 'no_note', 'whitespace_note',
    'long_note', 'no_custom_purpose', 'whitespace_custom_purpose', 'long_custom_purpose', 'extra_field'])
def test_schema_rejection_creates_no_job(referenced, failure):
    (setup, _, annotation), body, _ = referenced
    client, factory, _, task, material, _ = setup
    ref = body['imageEdits'][0]['references'][0]
    if failure == 'missing_attachment':
        body['attachmentIds'].remove(ref['attachmentId'])
    elif failure in ('invalid_id', 'material'):
        ref['attachmentId'] = 'upload:bad' if failure == 'invalid_id' else 'task:' + material['id']
        body['attachmentIds'].append(ref['attachmentId'])
    elif failure == 'duplicate':
        body['imageEdits'][0]['references'].append(copy.deepcopy(ref))
    elif failure == 'uuid_alias_duplicate':
        other = dict(ref, attachmentId='upload:' + UUID(ref['attachmentId'][7:]).hex.upper())
        body['imageEdits'][0]['references'].append(other)
        body['attachmentIds'].append(other['attachmentId'])
    elif failure == 'annotation':
        # A reference attached to another target also cannot reuse an annotation.
        body['imageEdits'][1]['references'][0]['attachmentId'] = annotation['id']
    elif failure == 'unknown_kind':
        ref['kind'] = 'unknown'
    elif failure in ('no_note', 'whitespace_note', 'long_note'):
        ref['note'] = {'no_note': '', 'whitespace_note': ' \n ', 'long_note': '字' * 2001}[failure]
    elif failure in ('no_custom_purpose', 'whitespace_custom_purpose', 'long_custom_purpose'):
        ref['kind'] = 'custom'
        ref['customPurpose'] = {'no_custom_purpose': None, 'whitespace_custom_purpose': ' \n ',
            'long_custom_purpose': '字' * 2001}[failure]
    elif failure == 'extra_field':
        ref['inputIndex'] = 0
    response = send(client, task, key='invalid-ref', **body)
    assert response.status_code == 422, response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


@pytest.mark.parametrize('failure', ['cross_task', 'cross_conversation', 'missing', 'corrupt_image', 'document'])
def test_reference_access_and_content_rejection(referenced, failure):
    (setup, _, _), body, uploaded = referenced
    client, factory, _, task, _, _ = setup
    expected = 404
    identity = uploaded[0][0]['id']
    body['conversationId'] = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()['conversationId']
    if failure in ('cross_task', 'cross_conversation'):
        with factory.begin() as session:
            upload = session.get(Upload, UUID(identity[7:]))
            if failure == 'cross_task':
                source = session.get(Task, UUID(task['id']))
                other = Task(name='other', product_name='phone', brand='brand', platform='Amazon',
                    market='US', created_by=source.created_by, designer_id=source.designer_id)
                session.add(other)
                session.flush()
                upload.task_id = other.id
            else:
                channel = Conversation(task_id=UUID(task['id']), name='其他会话')
                session.add(channel)
                session.flush()
                upload.conversation_id = channel.id
    else:
        new_id = 'upload:' + str(uuid4())
        if failure != 'missing':
            name = 'broken.png' if failure == 'corrupt_image' else 'notes.txt'
            response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
                files={'file': (name, b'not an image')}, headers=HEADERS)
            assert response.status_code == 200, response.text
            new_id, expected = response.json()['id'], 422
        body['attachmentIds'][body['attachmentIds'].index(identity)] = new_id
        for edit in body['imageEdits']:
            for ref in edit['references']:
                if ref['attachmentId'] == identity:
                    ref['attachmentId'] = new_id
    response = send(client, task, key='access-ref', **body)
    assert response.status_code == expected, response.text
    if failure == 'cross_conversation':
        assert '附件不属于当前会话' in str(response.json())
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


@pytest.mark.parametrize('format,extension', [('PNG', 'png'), ('JPEG', 'jpg'), ('WEBP', 'webp')])
def test_supported_real_reference_formats(editable, format, extension):
    (client, _, _, task, _, _), pictures, _ = editable
    content = BytesIO()
    Image.new('RGB', (3, 5), 'purple').save(content, format=format)
    response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
        files={'file': ('reference.' + extension, content.getvalue())}, headers=HEADERS)
    assert response.status_code == 200, response.text
    identity = response.json()['id']
    response = send(client, task, key='format', referencePictureIds=[pictures[0]['id']],
        attachmentIds=[identity], imageEdits=[dict(pictureId=pictures[0]['id'], references=[
            dict(attachmentId=identity, kind='custom', customPurpose='用' * 2000, note='注' * 2000)])])
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('extra,expected', [(0, 200), (1, 422)])
def test_actual_reference_file_twenty_mib_boundary(editable, extra, expected):
    (client, _, _, task, _, _), pictures, _ = editable
    content = BytesIO()
    Image.new('RGB', (3, 5), 'purple').save(content, format='PNG')
    data = content.getvalue().ljust(20 * 1024 * 1024 + extra, b'\0')
    response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
        files={'file': ('reference.png', data)}, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()['contentType'] == 'image/png'
    identity = response.json()['id']
    response = send(client, task, key='size', referencePictureIds=[pictures[0]['id']],
        attachmentIds=[identity], imageEdits=[dict(pictureId=pictures[0]['id'], references=[
            dict(attachmentId=identity, kind='product', note='参照结构')])])
    assert response.status_code == expected, response.text


def test_freeze_checks_uuid_identity_not_only_index(referenced):
    (setup, pictures, _), body, _ = referenced
    _, factory, _, _, _, _ = setup
    from app.overseas.studio.models import Picture
    with factory() as session:
        attachments = [session.get(Upload, UUID(value[7:])) for value in body['attachmentIds']]
        sources = [session.get(Picture, UUID(value['id'])) for value in pictures]
        attachments[1], attachments[2] = attachments[2], attachments[1]
        with pytest.raises(HTTPException, match='身份不匹配'):
            freeze_edits(Send(**body), attachments, sources)
