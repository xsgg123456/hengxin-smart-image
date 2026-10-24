"""Real runner/API regressions for file output and the production ImageView incident."""
import base64
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

import pytest
from PIL import Image
from app.overseas.execution import runner
from app.overseas.studio.models import OutputFile
from studio_delivery_helpers import DeliveryCase, studio, materials, overseas, send


def append_files(case, monkeypatch, files):
    original = runner.execute

    def execute(*args):
        receipt = original(*args)
        workspace = case.workspace
        path = workspace.control / 'events.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()]
        final = next(row['item'] for row in events if row.get('item', {}).get('type') == 'agent_message')
        for name, data in files.items():
            (workspace.work / name).write_bytes(data)
            final['text'] += f'\n[下载](/work/{name})'
        path.write_text('\n'.join(json.dumps(row) for row in events), encoding='utf-8')
        return receipt
    monkeypatch.setattr(runner, 'execute', execute)


def test_mixed_picture_zip_unknown_and_empty_outputs_download_originals(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=1)
    before_materials = case.view()['materials']
    zipped = BytesIO()
    with ZipFile(zipped, 'w') as archive:
        archive.writestr('readme.txt', 'original delivery')
    data = {'design.zip': zipped.getvalue(), 'project.xyz': b'original project',
            'empty.txt': b'', 'broken.png': b'not decodable'}
    append_files(case, monkeypatch, data)
    case.run()
    turn = case.current()
    assert turn['status'] == 'succeeded'
    assert turn['deliveryStatus'] == dict(state='complete', expected=5, saved=5)
    assert len(turn['pictures']) == 1 and len(turn['outputs']) == 4
    assert turn['pictures'][0]['name'] == 'output0.png'
    for row in turn['outputs']:
        response = case.client.get(row['url'])
        assert response.status_code == 200 and response.content == data[row['name']]
        assert response.headers['content-disposition'].startswith('attachment')
        assert case.client.head(row['url']).status_code == 200
    assert case.count(OutputFile) == 4 and case.view()['materials'] == before_materials
    assert send(case.client, case.task, key='after-mixed').status_code == 200


def test_tool_view_of_material_does_not_create_missing_image_or_block(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)
    original = runner.execute

    def execute(*args):
        receipt = original(*args)
        path = case.workspace.home / '.codex/sessions/rollout-session-123.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        turn_id = case.workspace.control.name
        rows[2:2] = [
            dict(type='event_msg', payload=dict(type='item_completed', turn_id=turn_id,
                thread_id='session-123', item=dict(type='ImageView', path='file:///work/material.png'))),
            dict(type='response_item', payload=dict(type='custom_tool_call_output', call_id='view-call',
                internal_chat_message_metadata_passthrough=dict(turn_id=turn_id), output=[
                    dict(type='input_image', image_url='data:image/png;base64,' +
                         base64.b64encode(b'\x89PNG\r\n\x1a\nmaterial').decode())]))]
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
        return receipt

    monkeypatch.setattr(runner, 'execute', execute)
    case.run()
    case.complete(expected=0)
    assert not case.current()['deliveryError']
    assert send(case.client, case.task, key='after-material').status_code == 200


def test_exact_production_incident_input(studio, monkeypatch, tmp_path):
    """Private raw record is read from ignored output, never distributed in source."""
    fixture = os.environ.get('STUDIO_INCIDENT_FIXTURE')
    if not fixture:
        pytest.skip('Set STUDIO_INCIDENT_FIXTURE to the preserved production record')
    data = json.loads(gzip.decompress(Path(fixture).read_bytes()))
    raw = base64.b64decode(data['files']['rollout.jsonl'])
    assert sha256(raw).hexdigest() == '386aec1caa31ecc6c8f7701d8ee5c1728c3607e02e0724e87eb9d849ae4a611f'
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)

    def execute(_command, _prompt, control, _timeout, monitor, started):
        started(123, 'boot', 'birth')
        assert not monitor()
        (control / 'events.jsonl').write_bytes(base64.b64decode(data['files']['events.jsonl']))
        directory = case.workspace.home / '.codex/sessions'
        directory.mkdir(parents=True)
        (directory / f"rollout-{data['sessionId']}.jsonl").write_bytes(raw)
        for name, value in data['files'].items():
            if name.startswith('work/'):
                path = case.workspace.work / name[5:]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(value))
        return json.loads(base64.b64decode(data['files']['delivery-exit.json']))

    monkeypatch.setattr(runner, 'execute', execute)
    case.run()
    turn = case.current()
    assert turn['status'] == 'succeeded' and turn['reply'] == data['finalText']
    assert turn['pictures'] == [] and case.view()['activeTurnId'] is None
    assert case.job().execution_count == 1 and len(case.commands) == 1
    assert not (case.job().result or {}).get('deliveryRetryAt')
    expected_files = [name for name in data['files'] if name.startswith('work/')]
    assert len(turn['outputs']) == len(expected_files) == 1
    assert turn['deliveryStatus'] == dict(state='complete', expected=1, saved=1)
    assert case.client.get(turn['outputs'][0]['url']).content == base64.b64decode(data['files'][expected_files[0]])
    assert send(case.client, case.task, key='after-real-incident').status_code == 200


def test_output_download_requires_current_task_access(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)
    append_files(case, monkeypatch, {'package.zip': b'original'})
    case.run()
    row = case.current()['outputs'][0]
    other = row['url'].replace(case.task['id'], '00000000-0000-0000-0000-000000000001')
    assert case.client.get(other).status_code in (403, 404)


def test_non_picture_output_cannot_replace_archived_image_requirement(studio, monkeypatch, tmp_path):
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)
    append_files(case, monkeypatch, {'package.zip': b'original'})
    case.run()
    response = case.client.post(case.root + '/complete', json={'version': case.view()['taskVersion']},
        headers={'Idempotency-Key': 'no-image-complete', 'X-HX-Request': '1'})
    assert response.status_code == 409


def test_valid_image_above_old_ten_mib_limit_keeps_picture_operations(studio, monkeypatch, tmp_path):
    buffer = BytesIO()
    Image.frombytes('RGB', (2048, 2048), os.urandom(2048 * 2048 * 3)).save(buffer, format='PNG')
    original = buffer.getvalue()
    assert len(original) > 10 * 1024 * 1024
    case = DeliveryCase(studio, monkeypatch, tmp_path, count=0)
    append_files(case, monkeypatch, {'large.png': original})
    case.run()
    turn = case.current()
    assert turn['status'] == 'succeeded' and turn['deliveryStatus']['state'] == 'complete'
    assert len(turn['pictures']) == 1 and turn['outputs'] == []
    picture = turn['pictures'][0]
    assert (picture['width'], picture['height']) == (2048, 2048)
    assert case.client.get(picture['url']).content == original
