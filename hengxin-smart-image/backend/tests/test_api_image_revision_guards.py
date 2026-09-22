from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api, upload
from test_api_image_versions import post, setup_result


@pytest.mark.parametrize('sibling_state', ['running', 'uncertain'])
@pytest.mark.parametrize('action', ['revise', 'retry'])
def test_enqueue_preserves_active_sibling_and_blocks_delete(files_env, sibling_state, action):
    client, factory, _, _ = files_env
    task_id, first, path = setup_result(client, factory, count=2)
    with factory.begin() as session:
        task = session.get(ApiTask, UUID(task_id))
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)
                                .order_by(ApiItem.position)).all()
        task.state, task.started_at = sibling_state, utcnow()
        items[1].state = sibling_state
        if action == 'retry':
            items[0].state = 'failed'
    data = {'baseVersion': 1, 'text': '修改'} if action == 'revise' else None
    assert post(client, path + '/' + action, data).status_code == 202
    assert client.get(f'{ROOT}/tasks/{task_id}').json()['status'] == sibling_state
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
    # Even an incorrectly cached task state cannot hide an in-flight child.
    with factory.begin() as session:
        session.get(ApiTask, UUID(task_id)).state = 'queued'
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
    fresh, _ = create(client, count=1)
    assert client.delete(f'{ROOT}/tasks/{fresh}').status_code == 200


@pytest.mark.parametrize('kind,size', [('image/webp', 100), ('image/png', 10 * 1024 * 1024 + 1)])
def test_revision_rejects_annotation_format_and_size_server_side(files_env, kind, size):
    client, factory, _, _ = files_env
    task_id, _, path = setup_result(client, factory)
    annotation = upload(client, 'annotation.png')
    with factory.begin() as session:
        record = session.get(ApiFile, UUID(annotation['fileId']))
        record.content_type, record.size_bytes = kind, size
    result = post(client, path + '/revise', {'baseVersion': 1, 'annotationFileId': annotation['fileId']})
    assert result.status_code == 422
    assert client.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]['state'] == 'succeeded'


def test_revision_accepts_jpeg_annotation_without_text(files_env):
    client, factory, _, _ = files_env
    _, _, path = setup_result(client, factory)
    annotation = client.post(ROOT + '/files', files={'file': ('mark.jpg', image_bytes('JPEG'), 'image/jpeg')}).json()
    assert post(client, path + '/revise', {'baseVersion': 1, 'annotationFileId': annotation['fileId']}).status_code == 202
