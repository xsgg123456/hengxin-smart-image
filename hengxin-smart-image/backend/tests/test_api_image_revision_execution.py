from uuid import UUID, uuid4
from datetime import timedelta

from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.relay import RelayError, RelayResult
from app.modules.api_image_edits.models import ApiItem
from app.models import utcnow
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api, upload
from test_api_image_execution import Client


def test_failed_revision_preserves_version_then_retry_uses_frozen_result_and_annotation(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 2)
    first = Client([RelayResult(image_bytes=image_bytes('JPEG'))])
    assert execute_next(factory, store, first)
    assert execute_next(factory, store, first)
    path = ROOT + '/tasks/' + task_id
    task = web.get(path).json()
    item, neighbor = task['items']
    current_bytes = web.get(item['result']['url']).content
    assert current_bytes != web.get(item['source']['url']).content
    annotation = upload(web, 'annotation.png')
    endpoint = path + '/items/' + item['id']
    body = {'baseVersion': 1, 'text': '请修正边缘', 'annotationFileId': annotation['fileId']}
    assert web.post(endpoint + '/revise', json=body, headers={'Idempotency-Key': str(uuid4())}).status_code == 202
    failures = Client([RelayError('retryable', 'HTTP_503', 'safe')] * 4)
    for _ in range(4):
        assert execute_next(factory, store, failures)
        with factory.begin() as session:
            session.get(ApiItem, UUID(item['id'])).next_attempt_at = utcnow() - timedelta(seconds=1)
    failed = web.get(path).json()
    assert failed['items'][0]['state'] == 'failed'
    assert failed['items'][0]['result'] == item['result']
    assert failed['items'][0]['versions'] == item['versions']
    assert failed['items'][1] == neighbor
    assert len(failures.calls) == 4
    assert all(args[0] == current_bytes and args[2] == image_bytes() and args[4] == body['text'] for args in failures.calls)
    assert web.post(endpoint + '/retry', headers={'Idempotency-Key': str(uuid4())}).status_code == 202
    recovered = Client()
    assert execute_next(factory, store, recovered)
    result = web.get(path).json()
    assert result['status'] == 'succeeded'
    assert result['items'][0]['currentVersion'] == 2
    assert result['items'][0]['versions'][0] == item['versions'][0]
    assert result['items'][0]['versions'][1]['baseVersion'] == 1
    assert result['items'][1] == neighbor
    assert recovered.calls[0][0] == current_bytes
