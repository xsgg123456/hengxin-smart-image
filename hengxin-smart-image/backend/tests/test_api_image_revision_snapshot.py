import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.image_revision_prompt import REVISION_POLICY_VERSION
from app.modules.api_image_edits.execution import execute_next, inputs
from app.modules.api_image_edits.models import ApiFile, ApiItem, ApiTask
from app.modules.api_image_edits.relay import RelayClient
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, enabled_api, upload
from test_api_image_execution import Client
from test_api_image_relay import config, response
from test_api_image_versions import post, setup_result


@pytest.mark.parametrize('annotated', [False, True])
def test_snapshot_final_wire_order_and_prompt(files_env, annotated):
    web, factory, store, _ = files_env
    task_id, first, path = setup_result(web, factory)
    # Give each role different bytes, including a distinct current result.
    current = web.post(ROOT + '/files', files={'file': ('current.jpg', image_bytes('JPEG'), 'image/jpeg')}).json()
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        item.result_id = UUID(current['fileId'])
        ids = [item.result_id, item.source_id, session.get(ApiTask, item.task_id).material_id]
    body = {'baseVersion': 1, 'text': '修复边缘'}
    if annotated:
        annotation = upload(web, 'annotation.png')
        body = {'baseVersion': 1, 'annotationFileId': annotation['fileId']}
        ids.append(UUID(annotation['fileId']))
    assert post(web, path + '/revise', body).status_code == 202
    with factory() as session:
        frozen = session.get(ApiItem, UUID(first['id'])).revision_snapshot
        assert frozen['fileIds'] == list(map(str, ids))
        assert frozen['policyVersion'] == REVISION_POLICY_VERSION
        assert frozen['prompt'] and '图1' in frozen['prompt'] and '图3' in frozen['prompt']
        if annotated:
            assert '图4' in frozen['prompt'] and '定位' in frozen['prompt']
            assert '自由画笔' in frozen['prompt'] and '不是像素蒙版' in frozen['prompt']
            assert frozen['policyVersion'] == 'single-image-reference-v2'
    opened = []
    original_open = store.open
    def capture(record):
        opened.append(record.id)
        return original_open(record)
    store.open = capture
    pool = Mock()
    pool.request.return_value = response(payload={'data': [{'b64_json': base64.b64encode(image_bytes()).decode()}]})
    assert execute_next(factory, store, RelayClient(config(), pool))
    wire = json.loads(pool.request.call_args.kwargs['body'])
    assert opened == ids
    assert wire['prompt'] == frozen['prompt']
    assert len(wire['images']) == len(ids)
    assert base64.b64decode(wire['images'][0]['image_url'].split(',')[1]) == image_bytes('JPEG')
    assert all(base64.b64decode(entry['image_url'].split(',')[1]) == image_bytes() for entry in wire['images'][1:])


@pytest.mark.parametrize('role', [0, 1, 2, 3])
@pytest.mark.parametrize('damage', ['deleted', 'missing', 'checksum', 'decode'])
def test_each_snapshot_input_failure_never_calls_upstream(files_env, role, damage):
    web, factory, store, _ = files_env
    _, first, path = setup_result(web, factory)
    current, annotation = upload(web, 'current.png'), upload(web, 'annotation.png')
    with factory.begin() as session:
        session.get(ApiItem, UUID(first['id'])).result_id = UUID(current['fileId'])
    assert post(web, path + '/revise', {'baseVersion': 1, 'annotationFileId': annotation['fileId']}).status_code == 202
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        record = session.get(ApiFile, UUID(item.revision_snapshot['fileIds'][role]))
        if damage == 'deleted':
            record.status = 'failed'
        elif damage == 'missing':
            del store.objects[record.object_key]
        else:
            store.objects[record.object_key] = b'corrupt bytes'
            if damage == 'decode':
                record.size_bytes = len(b'corrupt bytes')
                record.checksum = hashlib.sha256(b'corrupt bytes').hexdigest()
    relay = Client()
    assert execute_next(factory, store, relay)
    assert not relay.calls
    with factory() as session:
        item = session.get(ApiItem, UUID(first['id']))
        assert item.state == 'failed' and item.error == 'input_storage_unavailable'
        assert str(item.result_id) == current['fileId']


@pytest.mark.parametrize('role', ['source', 'material'])
def test_acceptance_checks_original_and_material_status(files_env, role):
    web, factory, _, _ = files_env
    _, first, path = setup_result(web, factory)
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        target = item.source_id if role == 'source' else session.get(ApiTask, item.task_id).material_id
        session.get(ApiFile, target).status = 'failed'
    assert post(web, path + '/revise', {'baseVersion': 1, 'text': '修复'}).status_code == 404


@pytest.mark.parametrize('old_policy', [False, True])
def test_snapshot_freezes_ids_prompt_and_protects_standalone_reference(files_env, monkeypatch, old_policy):
    web, factory, store, _ = files_env
    _, first, path = setup_result(web, factory)
    assert post(web, path + '/revise', {'baseVersion': 1, 'text': '修复'}).status_code == 202
    if old_policy:
        with factory.begin() as session:
            item = session.get(ApiItem, UUID(first['id']))
            item.revision_snapshot = {**item.revision_snapshot,
                                      'prompt': '升级前已受理的原提示词，保持原文。',
                                      'policyVersion': 'single-image-reference-v1'}
    frozen_args = inputs(factory, UUID(first['id']), store)
    monkeypatch.setattr('app.modules.api_image_edits.versions.build_revision_prompt',
                        lambda **kwargs: pytest.fail('retry rebuilt frozen prompt'))
    extra = upload(web, 'new-material.png')
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        old_material = item.revision_snapshot['fileIds'][2]
        task = session.get(ApiTask, item.task_id)
        task.material_id, task.prompt = UUID(extra['fileId']), 'changed task prompt'
        item.revision_text, item.state, task.state = 'changed text', 'failed', 'partial_failed'
    assert web.delete(ROOT + '/files/' + old_material).status_code == 409
    assert post(web, path + '/retry').status_code == 202
    assert inputs(factory, UUID(first['id']), store) == frozen_args


@pytest.mark.parametrize('annotated', [False, True])
def test_null_snapshot_preserves_legacy_six_arguments(files_env, annotated):
    web, factory, store, _ = files_env
    _, first, _ = setup_result(web, factory)
    annotation = upload(web, 'annotation.png') if annotated else None
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(first['id']))
        item.revision_base_version, item.revision_source_id = 1, item.result_id
        item.revision_annotation_id = UUID(annotation['fileId']) if annotation else None
        item.revision_text, item.revision_snapshot = '历史原文', None
    args = inputs(factory, UUID(first['id']), store)
    assert len(args) == 6 and args[4] == '历史原文'
    assert args[2] == (image_bytes() if annotated else None)


def test_0017_migration_preserves_old_row_and_roundtrips():
    path = Path(__file__).parents[1] / 'migrations/versions/0017_api_revision_snapshot.py'
    spec = importlib.util.spec_from_file_location('revision_snapshot_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE api_image_items (id INTEGER PRIMARY KEY, revision_text TEXT)'))
        connection.execute(text("INSERT INTO api_image_items VALUES (1, 'legacy')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
            assert connection.execute(text('SELECT revision_text, revision_snapshot FROM api_image_items')).one() == ('legacy', None)
            connection.execute(text("UPDATE api_image_items SET revision_snapshot = :snapshot"),
                               {'snapshot': json.dumps({'fileIds': ['frozen']})})
            with pytest.raises(RuntimeError, match='Cannot discard'):
                module.downgrade()
            connection.execute(text("UPDATE api_image_items SET revision_snapshot = 'null'"))
            module.downgrade()
            module.downgrade()
            assert 'revision_snapshot' not in {column['name'] for column in inspect(connection).get_columns('api_image_items')}
            module.upgrade()
            assert connection.execute(text('SELECT revision_snapshot FROM api_image_items')).scalar() is None
    engine.dispose()
