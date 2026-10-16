"""HTTP visibility changes preserve immutable inputs and independent task scopes."""
from copy import deepcopy
from uuid import UUID
import pytest
from sqlalchemy import select, func
from app.overseas.materials.models import Material
from app.overseas.studio.models import MaterialVisibility, Upload, Turn
from app.overseas.studio import context_workspace
from app.overseas.execution.models import Job
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, create, payload, ROOT, HEADERS
from test_overseas_materials import materials, upload
from test_overseas_studio import studio, send, finish
from test_overseas_assignment import change_roles
from test_overseas_plans import post
from test_studio_context_assets import workspace, original_path


def path(task):
    return ROOT + '/tasks/' + task['id'] + '/studio'


def add(client, task, data=b'new content', name='notes.txt'):
    response = client.post(path(task) + '/files', files={'file': (name, data)}, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def remove(client, task, identity):
    return client.delete(path(task) + '/materials/' + identity, headers=HEADERS)


def test_cross_source_and_legacy_duplicates_use_content_not_name(studio):
    client, factory, actor, task, material, _ = studio
    first = add(client, task, b'name,value\nitem,42\n', 'different.txt')
    assert first['materialState'] == 'existing' and first['id'].startswith('upload:')
    second = add(client, task)
    third = add(client, task, b'other content')
    assert second['materialState'] == third['materialState'] == 'added'
    # Simulate pre-migration duplicate Upload records without visibility metadata.
    with factory.begin() as session:
        old = session.get(Upload, UUID(second['id'].split(':')[1]))
        session.add(Upload(task_id=old.task_id, name='legacy alias.txt', content_type=old.content_type,
            checksum=old.checksum, size_bytes=old.size_bytes, bucket=old.bucket,
            object_key='studio/uploads/legacy'))
    view = client.get(path(task)).json()
    assert [a['id'] for a in view['materials']] == ['task:' + material['id'], second['id'], third['id']]
    assert [a['name'] for a in view['materials']][1:] == ['notes.txt', 'notes.txt']
    hidden = remove(client, task, first['id'])
    assert hidden.status_code == 200 and len(hidden.json()['materials']) == 2
    assert remove(client, task, 'task:' + material['id']).json()['materials'] == hidden.json()['materials']
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MaterialVisibility)) == 1
        assert session.get(Material, UUID(material['id'])).deleted_at is None
    restored = add(client, task, b'name,value\nitem,42\n', 'renamed.txt')
    assert restored['materialState'] == 'restored' and restored['id'] != first['id']
    assert client.get(path(task)).json()['materials'][0]['id'] == 'task:' + material['id']
    assert add(client, task, b'name,value\nitem,42\n')['materialState'] == 'existing'


def test_removal_preserves_history_frozen_payload_and_persistent_inputs(studio, tmp_path):
    client, factory, _, task, material, store = studio
    uploaded = add(client, task)
    identities = ['task:' + material['id'], uploaded['id']]
    turn = send(client, task, attachmentIds=identities).json()['turns'][0]
    previews = {a['id']: client.get(a['url'] + '?preview=true').status_code for a in turn['attachments']}
    with factory() as session:
        frozen = deepcopy(session.get(Job, UUID(turn['jobId'])).payload)
    ws = workspace(tmp_path, turn['conversationId'], turn['id'])
    prepared = context_workspace.prepare(ws, [], frozen['inputs'], lambda row: store.data[row['object_key']])
    originals = {original_path(ws, row): original_path(ws, row).read_bytes() for row in prepared}
    (ws.work / 'remember.txt').write_text('keep editable work')
    index = ws.context_index.read_bytes()
    for identity in identities:
        assert remove(client, task, identity).status_code == 200
    state = client.get(path(task)).json()
    assert state['materials'] == [] and state['activeTurnId'] == turn['id']
    assert state['turns'][0]['attachments'] == turn['attachments']
    for asset in turn['attachments']:
        assert client.get(asset['url']).status_code == 200
        assert client.get(asset['url'] + '?preview=true').status_code == previews[asset['id']]
    with factory() as session:
        assert session.get(Job, UUID(turn['jobId'])).payload == frozen
        assert session.get(Turn, UUID(turn['id'])).attachment_ids == identities
    assert ws.context_index.read_bytes() == index
    assert all(target.read_bytes() == data for target, data in originals.items())
    assert (ws.work / 'remember.txt').read_text() == 'keep editable work'
    finish(factory, turn)
    later = send(client, task, key='old-reference', attachmentIds=identities).json()
    assert later['materials'] == [] and later['turns'][-1]['attachments'] == turn['attachments']
    followup = workspace(tmp_path, turn['conversationId'])
    context_workspace.prepare(followup, [dict(turn_id=turn['id'], inputs=frozen['inputs'])], [],
                              lambda _: pytest.fail('original bytes should remain locally available'))
    assert all(target.read_bytes() == data for target, data in originals.items())
    finish(factory, later['turns'][-1])
    assert post(client, task, '/studio/conversations', {}, 'new').json()['materials'] == []
    assert client.get(path(task)).json()['materials'] == []


def test_task_boundary_and_shared_visibility(studio):
    client, factory, actor, task, material, _ = studio
    other = create(client, payload(UUID(task['designer']['id'])), 'other-task').json()
    with factory.begin() as session:
        row = session.get(Task, UUID(other['id']))
        row.status, row.requirements_approved = 'studio', True
    other_file = add(client, other, b'name,value\nitem,42\n')
    assert other_file['materialState'] == 'added'
    assert remove(client, other, 'task:' + material['id']).status_code == 404
    assert remove(client, task, other_file['id']).status_code == 404
    assert remove(client, task, 'task:' + material['id']).json()['materials'] == []
    assert [a['id'] for a in client.get(path(other)).json()['materials']] == [other_file['id']]
    change_roles(factory, actor, ('operator',))
    assert client.get(path(task)).json()['materials'] == []
    assert remove(client, task, 'task:' + material['id']).status_code == 403


def test_hidden_image_keeps_preview_and_failed_upload_does_not_restore(studio, monkeypatch):
    from io import BytesIO
    from PIL import Image
    client, _, _, task, _, store = studio
    buffer = BytesIO()
    Image.new('RGB', (8, 8), 'blue').save(buffer, 'PNG')
    content = buffer.getvalue()
    image = add(client, task, content, 'original.png')
    assert remove(client, task, image['id']).status_code == 200
    assert client.get(image['url'] + '?preview=true').content == content
    assert client.head(image['url'] + '?preview=true').status_code == 200
    original_put = store.put
    def fail(*_):
        raise OSError('store unavailable')
    monkeypatch.setattr(store, 'put', fail)
    response = client.post(path(task) + '/files', files={'file': ('renamed.png', content)}, headers=HEADERS)
    assert response.status_code == 503
    assert all(a['id'] != image['id'] for a in client.get(path(task)).json()['materials'])
    monkeypatch.setattr(store, 'put', original_put)
    assert add(client, task, content, 'renamed.png')['materialState'] == 'restored'
    assert image['id'] in [a['id'] for a in client.get(path(task)).json()['materials']]


@pytest.mark.parametrize('role,assigned,allowed', [('designer', True, True), ('designer', False, False),
    ('operator', True, False), ('design_manager', False, True), ('super_admin', False, True)])
def test_remove_requires_task_design_permission(studio, role, assigned, allowed):
    client, factory, actor, task, material, _ = studio
    if assigned:
        with factory.begin() as session:
            session.get(Task, UUID(task['id'])).designer_id = actor
    change_roles(factory, actor, (role,))
    assert remove(client, task, 'task:' + material['id']).status_code == (200 if allowed else 403)


def test_remove_validation_browser_and_completed_guards(studio):
    client, factory, _, task, material, _ = studio
    url = path(task) + '/materials/' + 'task:' + material['id']
    assert client.delete(url).status_code == 403
    for identity in ('invalid', 'picture:' + material['id'], 'upload:invalid'):
        assert remove(client, task, identity).status_code == 422
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).status = 'completed'
    assert client.delete(url, headers=HEADERS).status_code == 409
    assert len(client.get(path(task)).json()['materials']) == 1


def test_permanent_task_deletion_cleans_visibility(studio, tmp_path):
    from app.core.config import get_settings
    from app.overseas.tasks.cleanup import cleanup_once
    from test_overseas_task_deletion import request
    client, factory, _, task, material, store = studio
    get_settings().codex_execution_root = str(tmp_path / 'execution')
    assert remove(client, task, 'task:' + material['id']).status_code == 200
    assert request(client, task).status_code == 200
    assert cleanup_once(factory, store) == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MaterialVisibility)) == 0
