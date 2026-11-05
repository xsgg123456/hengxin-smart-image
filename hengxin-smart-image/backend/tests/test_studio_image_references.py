"""HTTP reference contracts, immutable history and byte-accurate prompt binding."""
import copy
import json
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload
from app.overseas.execution.models import Job
from app.overseas.studio import execution
from app.overseas.studio.models import Upload, Picture
from app.overseas.tasks.models import TaskRequest
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials
from test_overseas_studio import studio, send
from test_studio_image_edits import editable, request


@pytest.fixture
def referenced(editable):
    (client, _, _, task, _, _), pictures, annotation = editable
    body = request(pictures, annotation)
    uploaded = []
    for color, kind in [('red', 'product'), ('green', 'effect'), ('blue', 'custom')]:
        data = BytesIO()
        Image.new('RGB', (11, 13), color).save(data, format='PNG')
        response = client.post(ROOT + '/tasks/' + task['id'] + '/studio/files',
            files={'file': ('result.png', data.getvalue())}, headers=HEADERS)
        assert response.status_code == 200, response.text
        uploaded.append((response.json(), data.getvalue()))
        body['attachmentIds'].append(response.json()['id'])
        body['imageEdits'][0].setdefault('references', []).append(dict(
            attachmentId=response.json()['id'], kind=kind, note='参考说明' * 500,
            customPurpose='自定义完整用途\n' * 200 if kind == 'custom' else '不应进入提示词'))
    body['imageEdits'][1]['references'] = [dict(attachmentId=uploaded[0][0]['id'],
        kind='effect', note='第二张只参考这一张的颜色')]
    return editable, body, uploaded


def payload_for(factory, turn):
    with factory() as session:
        return copy.deepcopy(session.get(Job, UUID(turn['jobId'])).payload)


def prompt_data(prompt):
    return json.loads(prompt.split('图片修改要求：', 1)[1].split('\n', 1)[1].split('\n\n附件文件：')[0])


def test_http_freeze_context_files_prompt_and_public_history(referenced, tmp_path):
    from app.overseas.studio.context_assets import register, restore
    (setup, pictures, _), body, uploaded = referenced
    client, factory, _, task, _, store = setup
    response = send(client, task, key='references', **body)
    assert response.status_code == 200, response.text
    turn = response.json()['turns'][-1]
    frozen = payload_for(factory, turn)
    assert [r['inputIndex'] for r in frozen['imageEdits'][0]['references']] == [1, 2, 3]
    assert frozen['imageEdits'][1]['references'][0]['inputIndex'] == 1
    assert [e['pictureInputIndex'] for e in frozen['imageEdits']] == [4, 5]
    manifest = dict(assets={}, aliases={}, managed_turns=[])
    candidates, paths = register(manifest, [], frozen['inputs'], turn['id'], tmp_path)
    restore(tmp_path, manifest, candidates, lambda source: store.data[source['object_key']])
    prompt = execution.HANDLER.prepare(SimpleNamespace(payload=frozen),
        SimpleNamespace(input_paths=paths, previous_session='session'))
    edits = prompt_data(prompt)
    assert edits[0]['originalPath'] == paths[4]['path']
    assert edits[1]['originalPath'] == paths[5]['path']
    assert len({item['path'] for item in paths}) == 6  # All filenames are result.png.
    for index, (upload, original_bytes) in enumerate(uploaded, 1):
        assert (tmp_path / paths[index]['path'].removeprefix('/work/')).read_bytes() == original_bytes
        assert edits[0]['references'][index - 1]['path'] == paths[index]['path']
        assert client.get(upload['url']).content == original_bytes
    assert edits[1]['references'][0]['path'] == paths[1]['path']
    assert '不是额外待生成图片' in prompt and '不得跨图套用' in prompt
    for ref in body['imageEdits'][0]['references']:
        assert ref['note'] in prompt
        if ref['kind'] == 'custom':
            assert edits[0]['references'][2]['customPurpose'] == ref['customPurpose']
    assert '不应进入提示词' not in prompt
    assert turn['imageEdits'][0]['references'][0]['customPurpose'] == ''
    assert turn['imageEdits'][0]['references'][2]['customPurpose'] == body['imageEdits'][0]['references'][2]['customPurpose']
    serialized = json.dumps(turn['imageEdits'])
    for private in ('inputIndex', 'pictureInputIndex', 'bucket', 'object_key', '/work/', 'checksum'):
        assert private not in serialized
    assert send(client, task, key='references', **body).json() == response.json()
    changed = copy.deepcopy(body)
    changed['imageEdits'][0]['references'][0]['note'] = '修改后的说明'
    assert send(client, task, key='references', **changed).status_code == 409


def test_history_keeps_sent_metadata_and_files_after_material_hidden(referenced):
    (setup, pictures, _), body, uploaded = referenced
    client, factory, _, task, _, _ = setup
    result = send(client, task, key='history', **body).json()
    original = result['turns'][-1]
    with factory.begin() as session:
        session.get(Upload, UUID(uploaded[0][0]['id'][7:])).name = 'later-name.png'
        session.get(Picture, UUID(pictures[0]['id'])).name = 'renamed-original.png'
    response = client.delete(ROOT + '/tasks/' + task['id'] + '/studio/materials/' + uploaded[0][0]['id'],
        headers=HEADERS)
    assert response.status_code == 200, response.text
    history = client.get(ROOT + '/tasks/' + task['id'] + '/studio').json()
    current = history['turns'][-1]
    assert current['imageEdits'] == original['imageEdits']
    assert current['attachments'] == original['attachments']
    assert current['referencePictures'] == original['referencePictures']
    assert uploaded[0][0]['id'] not in [item['id'] for item in history['materials']]
    assert client.get(current['attachments'][1]['url']).content == uploaded[0][1]


def test_old_edit_fingerprint_replays_with_explicit_empty_references(editable):
    (client, factory, _, task, _, _), pictures, annotation = editable
    body = request(pictures, annotation)
    response = send(client, task, key='legacy-edit', **body)
    assert response.status_code == 200, response.text
    with factory() as session:
        record = session.scalar(select(TaskRequest).where(TaskRequest.key == 'legacy-edit'))
        assert record.body_hash == fingerprint_payload(dict(**body, skillId=None))
    for edit in body['imageEdits']:
        edit['references'] = []
    assert send(client, task, key='legacy-edit', **body).json() == response.json()


@pytest.mark.parametrize('tamper', ['index', 'identity', 'boolean', 'negative', 'out_of_bounds'])
def test_prompt_rejects_reference_index_or_identity_tampering(referenced, tamper):
    (setup, _, _), body, _ = referenced
    client, factory, _, task, _, _ = setup
    turn = send(client, task, key='binding', **body).json()['turns'][-1]
    frozen = payload_for(factory, turn)
    ref = frozen['imageEdits'][0]['references'][0]
    if tamper == 'identity':
        ref['attachmentId'] = body['attachmentIds'][2]
    else:
        ref['inputIndex'] = {'index': 2, 'boolean': True, 'negative': -1, 'out_of_bounds': 10}[tamper]
    with pytest.raises(ValueError, match='frozen input mismatch'):
        execution.HANDLER.prepare(SimpleNamespace(payload=frozen), SimpleNamespace(
            input_paths=[dict(path=f'/work/{i}') for i in range(6)], previous_session='session'))
