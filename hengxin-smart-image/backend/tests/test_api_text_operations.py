"""New API text operations exercise real request serialization and version delivery."""
import base64
import json
from io import BytesIO
from unittest.mock import Mock
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import select

from app.modules.api_image_edits.execution import execute_next, inputs
from app.modules.api_image_edits.models import ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.relay import RelayClient
from app.modules.api_image_edits.text_prompts import TEXT_REPAIR_PROMPT, build_text_prompt
from app.modules.api_image_edits.image_prompts import build_image_prompt
from files_helpers import files_env
from test_api_image_dimensions import encoded
from test_api_image_domain import ROOT, enabled_api
from test_api_image_relay import config, response
from test_api_image_versions import post


def upload_image(web, name, size, kind='PNG'):
    return web.post(ROOT + '/files', files={'file': (name, encoded(size, kind),
        'image/jpeg' if kind == 'JPEG' else 'image/png')}).json()['fileId']


@pytest.mark.parametrize('kind,annotated', [('image_edit', False), ('image_edit', True),
    ('text_edit', False), ('text_edit', True), ('text_repair', False)])
@pytest.mark.parametrize('source_size,request_size', [((790, 1500), '800x1520'), ((800, 800), '1024x1024')])
def test_text_wire_frozen_roles_source_dimensions_and_multiple_versions(files_env, kind, annotated, source_size, request_size):
    web, factory, store, _ = files_env
    original = upload_image(web, 'original.png', source_size)
    material = upload_image(web, 'material.png', (100, 100))
    task_id = post(web, ROOT + '/tasks', {'name': '文字', 'prompt': '创建',
        'originalFileIds': [original], 'materialFileId': material}).json()['taskId']
    current = upload_image(web, 'current.jpg', (500, 600), 'JPEG')
    annotation = upload_image(web, 'annotation.png', (500, 600)) if annotated else None
    with factory.begin() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == UUID(task_id)))
        item.result_id, item.state = UUID(current), 'succeeded'
        session.get(ApiTask, item.task_id).state = 'succeeded'
        item_id = item.id
    path = f'{ROOT}/tasks/{task_id}/items/{item_id}'
    text = {'image_edit': '移除指定装饰', 'text_edit': '把标题改为新标题', 'text_repair': ''}[kind]
    body = {'kind': kind, 'baseVersion': 1, 'text': text, 'prompt': '客户端试图删除全部保护'}
    if annotation:
        body['annotationFileId'] = annotation
    assert post(web, path + '/revise', body, 'one').status_code == 202
    assert post(web, path + '/revise', body, 'one').status_code == 202
    assert post(web, path + '/revise', {**body, 'kind': 'text_repair', 'annotationFileId': None}, 'another').status_code == 409
    expected = [current] + ([original, material] if kind == 'image_edit'
                            else [original] if kind == 'text_repair' else [])
    if annotation:
        expected.append(annotation)
    with factory() as session:
        snapshot = session.get(ApiItem, item_id).revision_snapshot
        assert snapshot['fileIds'] == expected and snapshot['kind'] == kind
        expected_prompt, expected_policy = (build_image_prompt(text) if kind == 'image_edit'
                                            else build_text_prompt(kind, text))
        assert snapshot['prompt'] == expected_prompt
        assert snapshot['policyVersion'] == expected_policy
        if kind == 'text_repair':
            assert snapshot['prompt'] == TEXT_REPAIR_PROMPT
    frozen = inputs(factory, item_id, store)
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        item.state = 'failed'
        item.revision_text = '之后修改不能改变冻结提示词'
    assert post(web, path + '/retry').status_code == 202
    assert inputs(factory, item_id, store) == frozen
    pool = Mock()
    pool.request.side_effect = lambda *args, **kwargs: response(payload={'data': [{'b64_json': base64.b64encode(encoded((333, 444), 'JPEG')).decode()}]})
    relay = RelayClient(config(), pool)
    assert execute_next(factory, store, relay)
    wire = json.loads(pool.request.call_args.kwargs['body'])
    assert wire['size'] == request_size and wire['prompt'] == snapshot['prompt']
    assert len(wire['images']) == len(expected)
    assert base64.b64decode(wire['images'][0]['image_url'].split(',')[1]) == encoded((500, 600), 'JPEG')
    if len(expected) == 2:
        expected_size = source_size if kind == 'text_repair' else (500, 600)
        assert base64.b64decode(wire['images'][1]['image_url'].split(',')[1]) == encoded(expected_size)
    if kind == 'image_edit':
        expected_bytes = [encoded((500, 600), 'JPEG'), encoded(source_size), encoded((100, 100))]
        if annotated:
            expected_bytes.append(encoded((500, 600)))
        assert [base64.b64decode(entry['image_url'].split(',')[1])
                for entry in wire['images']] == expected_bytes
    detail = web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    assert detail['currentVersion'] == 2 and detail['revision']['kind'] == kind
    assert [v['kind'] for v in detail['versions']] == ['generation', kind]
    with Image.open(BytesIO(web.get(detail['result']['url']).content)) as image:
        assert image.size == source_size and image.format == 'PNG'
    assert post(web, path + '/revise', {'baseVersion': 2, 'kind': kind, 'text': text}).status_code == 202
    assert execute_next(factory, store, relay)
    assert json.loads(pool.request.call_args.kwargs['body'])['size'] == request_size
    second = web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    with Image.open(BytesIO(web.get(second['result']['url']).content)) as image:
        assert image.size == source_size and image.format == 'PNG'
    assert post(web, path + '/restore', {'version': 1}).status_code == 200
    restored = web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    assert restored['currentVersion'] == 1 and restored['revision'] is None
    assert len(restored['versions']) == 3
    if kind == 'image_edit':
        assert post(web, path + '/revise', {'baseVersion': 1, 'kind': kind, 'text': text}).status_code == 202
        with factory() as session:
            assert session.get(ApiItem, item_id).revision_snapshot['fileIds'] == [current, original, material]


@pytest.mark.parametrize('body', [
    {'kind': 'text_edit', 'text': ''}, {'kind': 'text_edit', 'text': '  '},
    {'kind': 'text_edit', 'annotationFileId': '00000000-0000-0000-0000-000000000001'},
    {'kind': 'text_repair', 'annotationFileId': '00000000-0000-0000-0000-000000000001'},
    {'kind': 'revision', 'text': 'legacy cannot be newly submitted'},
])
def test_text_operation_schema_rejects_invalid_inputs(body):
    from pydantic import ValidationError
    from app.modules.api_image_edits.schemas import ReviseItem
    with pytest.raises(ValidationError):
        ReviseItem(baseVersion=1, **body)


@pytest.mark.parametrize('annotated_only', [False, True])
def test_pre_upgrade_unknown_request_confirms_old_key_without_rewriting(files_env, annotated_only):
    from app.modules.api_image_edits.models import ApiOperation
    from app.modules.api_image_edits.service import operation
    from app.resource_models import UserRecord
    from test_api_image_domain import upload
    from test_api_image_versions import setup_result
    web, factory, _, identity = files_env
    task_id, first, path = setup_result(web, factory)
    annotation = upload(web, 'old-annotation.png') if annotated_only else None
    body = {'baseVersion': 1, 'text': '' if annotated_only else '旧请求意见',
            'annotationFileId': annotation['fileId'] if annotation else None}
    with factory.begin() as session:
        user = session.get(UserRecord, identity[0])
        _, digest = operation(session, user, 'old-key',
            {'revise': task_id, 'item': first['id'], 'data': body})
        session.add(ApiOperation(operator_id=user.id, key='old-key', payload_hash=digest, task_id=UUID(task_id)))
        item = session.get(ApiItem, UUID(first['id']))
        task = session.get(ApiTask, item.task_id)
        snapshot = {'fileIds': list(map(str, [item.result_id, item.source_id, task.material_id])) +
                    ([annotation['fileId']] if annotation else []),
                    'prompt': '已受理旧原文', 'policyVersion': 'single-image-reference-v2'}
        item.revision_snapshot, item.revision_base_version, item.state = snapshot, 1, 'running'
    assert post(web, path + '/revise', body, 'old-key').status_code == 202
    assert post(web, path + '/revise', {**body, 'text': 'different'}, 'old-key').status_code == 409
    assert post(web, path + '/revise', {**body, 'kind': 'text_edit', 'text': 'new'}, 'old-key').status_code == 409
    with factory() as session:
        assert session.get(ApiItem, UUID(first['id'])).revision_snapshot == snapshot
    if annotated_only:
        assert post(web, path + '/revise', body, 'new-key').status_code == 422
