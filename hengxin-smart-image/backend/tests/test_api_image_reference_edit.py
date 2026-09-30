"""Reference-image v2 acceptance, immutable retries and pre-v2 execution."""
import hashlib
from uuid import UUID

import pytest

from app.models import utcnow
from app.modules.api_image_edits.execution import execute_next, inputs
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from app.modules.api_image_edits.versions import execution_inputs
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import ROOT, enabled_api, upload
from test_api_image_execution import Client, due
from app.modules.api_image_edits.relay import RelayError
from test_api_image_versions import post, setup_result


def prepare(web, factory, annotated=True):
    _, first, path = setup_result(web, factory)
    current = upload(web, 'current.png')
    annotation = upload(web, 'annotation.png') if annotated else None
    item_id = UUID(first['id'])
    with factory.begin() as session:
        session.get(ApiItem, item_id).result_id = UUID(current['fileId'])
    body = {'baseVersion': 1, 'kind': 'image_edit', 'text': '调整指定对象位置'}
    if annotation:
        body['annotationFileId'] = annotation['fileId']
    return item_id, path, body


@pytest.mark.parametrize('annotated', [False, True])
def test_v2_freezes_all_roles_across_automatic_manual_retry_and_confirmation(files_env, monkeypatch, annotated):
    web, factory, store, _ = files_env
    item_id, path, body = prepare(web, factory, annotated)
    assert post(web, path + '/revise', body, 'accepted').status_code == 202
    frozen = inputs(factory, item_id, store)
    with factory() as session:
        item = session.get(ApiItem, item_id)
        task = session.get(ApiTask, item.task_id)
        snapshot = item.revision_snapshot
        assert snapshot['policyVersion'] == 'api-image-edit-v2'
        assert snapshot['fileIds'][:3] == list(map(str, [item.result_id, item.source_id, task.material_id]))
        assert len(snapshot['fileIds']) == (4 if annotated else 3)
    extra = upload(web, 'different-material.png')
    monkeypatch.setattr('app.modules.api_image_edits.versions.build_image_prompt',
                        lambda *args: pytest.fail('must not rebuild accepted image prompt'))
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        session.get(ApiTask, item.task_id).material_id = UUID(extra['fileId'])
        item.revision_text = '之后改变的说明'
    assert post(web, path + '/revise', body, 'accepted').status_code == 202
    assert web.delete(ROOT + '/files/' + snapshot['fileIds'][2]).status_code == 409
    client = Client([RelayError('retryable', 'HTTP_503', 'safe')] * 4)
    for _ in range(4):
        assert execute_next(factory, store, client)
        due(factory)
    with factory() as session:
        assert session.get(ApiItem, item_id).state == 'failed'
    assert post(web, path + '/retry').status_code == 202
    recovered = Client()
    assert execute_next(factory, store, recovered)
    assert client.calls == [frozen] * 4 and recovered.calls == [frozen]
    with factory() as session:
        assert session.get(ApiItem, item_id).revision_snapshot == snapshot


@pytest.mark.parametrize('annotated', [False, True])
def test_v1_executes_and_retries_original_one_or_two_images_without_new_references(files_env, monkeypatch, annotated):
    web, factory, store, _ = files_env
    item_id, path, body = prepare(web, factory, annotated)
    assert post(web, path + '/revise', body, 'legacy-request').status_code == 202
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        ids = [str(item.result_id)] + ([body['annotationFileId']] if annotated else [])
        snapshot = {'kind': 'image_edit', 'policyVersion': 'api-image-edit-v1',
                    'fileIds': ids, 'prompt': '已冻结的旧版图片提示词，不补原图和素材。'}
        item.revision_snapshot = snapshot
        # v1 only needs source metadata for sizing, never its bytes or material.
        task = session.get(ApiTask, item.task_id)
        for file_id in [item.source_id, task.material_id]:
            record = session.get(ApiFile, file_id)
            record.status = 'failed'
            del store.objects[record.object_key]
    frozen = inputs(factory, item_id, store)
    assert frozen[4] == snapshot['prompt'] and frozen[6] is None
    assert (frozen[2] is not None) == annotated
    monkeypatch.setattr('app.modules.api_image_edits.versions.build_image_prompt',
                        lambda *args: pytest.fail('legacy policy must never be rebuilt'))
    assert post(web, path + '/revise', body, 'legacy-request').status_code == 202
    failed = Client([RelayError('retryable', 'HTTP_503', 'safe')] * 4)
    for _ in range(4):
        assert execute_next(factory, store, failed)
        due(factory)
    assert post(web, path + '/retry').status_code == 202
    recovered = Client()
    assert execute_next(factory, store, recovered)
    assert failed.calls == [frozen] * 4 and recovered.calls == [frozen]
    with factory() as session:
        assert session.get(ApiItem, item_id).revision_snapshot == snapshot


@pytest.mark.parametrize('role', range(4))
@pytest.mark.parametrize('damage', ['unready', 'deleted', 'missing', 'checksum', 'decode'])
def test_v2_each_missing_or_corrupt_input_rejects_without_upstream(files_env, role, damage):
    web, factory, store, _ = files_env
    item_id, path, body = prepare(web, factory)
    assert post(web, path + '/revise', body).status_code == 202
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        original_result = item.result_id
        record = session.get(ApiFile, UUID(item.revision_snapshot['fileIds'][role]))
        if damage == 'unready':
            record.status = 'failed'
        elif damage == 'deleted':
            record.deleted_at = utcnow()
        elif damage == 'missing':
            del store.objects[record.object_key]
        else:
            store.objects[record.object_key] = b'broken'
            if damage == 'decode':
                record.size_bytes = len(b'broken')
                record.checksum = hashlib.sha256(b'broken').hexdigest()
    client = Client()
    assert execute_next(factory, store, client)
    assert client.calls == []
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'failed' and item.error == 'input_storage_unavailable'
        assert item.result_id == original_result


@pytest.mark.parametrize('role', ['current', 'original', 'material', 'annotation'])
def test_v2_rejects_unavailable_file_metadata_before_acceptance(files_env, role):
    web, factory, _, _ = files_env
    item_id, path, body = prepare(web, factory)
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        task = session.get(ApiTask, item.task_id)
        file_id = {'current': item.result_id, 'original': item.source_id,
                   'material': task.material_id, 'annotation': UUID(body['annotationFileId'])}[role]
        session.get(ApiFile, file_id).status = 'failed'
    assert post(web, path + '/revise', body).status_code == 404
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'succeeded' and item.revision_snapshot is None


@pytest.mark.parametrize('policy,count', [('api-image-edit-v1', 3), ('api-image-edit-v2', 2), ('unknown', 3)])
def test_image_snapshot_policy_and_input_count_must_agree(files_env, policy, count):
    web, factory, _, _ = files_env
    item_id, path, body = prepare(web, factory)
    assert post(web, path + '/revise', body).status_code == 202
    with factory() as session:
        item = session.get(ApiItem, item_id)
        item.revision_snapshot = {**item.revision_snapshot, 'policyVersion': policy,
                                  'fileIds': item.revision_snapshot['fileIds'][:count]}
        with pytest.raises(ValueError, match='invalid revision snapshot'):
            execution_inputs(session, item, session.get(ApiTask, item.task_id))


def test_v2_rejects_client_reference_injection_and_requires_active_permission(files_env):
    web, factory, _, identity = files_env
    item_id, path, body = prepare(web, factory)
    for field in ['fileIds', 'originalFileId', 'materialFileId']:
        assert post(web, path + '/revise', {**body, field: body['annotationFileId']}).status_code == 422
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).status = 'disabled'
    assert post(web, path + '/revise', body).status_code == 403
    with factory() as session:
        assert session.get(ApiItem, item_id).revision_snapshot is None
