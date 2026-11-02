"""Full studio workflow and cross-task read-only HTTP/native boundaries."""
import time
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.studio import recovery_transport
from app.overseas.studio.models import OutputFile
from test_overseas_tasks import overseas, ROOT, HEADERS
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish, output
from test_overseas_assignment import change_roles
from test_overseas_plans import post
from test_overseas_workflow_grant import grant, relate


@pytest.mark.parametrize('relation', ['created', 'assigned'])
def test_granted_creator_and_assignee_complete_studio_workflow(studio, relation):
    client, factory, actor, task, material, store = studio
    other = UUID(task['designer']['id'])
    change_roles(factory, actor, ('designer',))
    grant(actor)
    relate(factory, task, actor, other, relation)
    base = ROOT + '/tasks/' + task['id'] + '/studio'
    created = post(client, task, '/studio/conversations', {'name': '创作'}, 'channel')
    assert created.status_code == 200, created.text
    channel = created.json()['conversationId']
    changed = client.patch(base + '/conversations/' + channel,
        json={'name': '新创作', 'version': 1}, headers={**HEADERS, 'Idempotency-Key': 'rename'})
    assert changed.status_code == 200, changed.text
    upload = client.post(base + '/files?conversationId=' + channel,
        files={'file': ('note.txt', b'workflow reference')}, headers=HEADERS)
    assert upload.status_code == 200, upload.text
    asset = upload.json()
    first = send(client, task, conversationId=channel, attachmentIds=[asset['id'], 'task:' + material['id']])
    assert first.status_code == 200, first.text
    turn = first.json()['turns'][-1]
    cancelled = post(client, task, '/studio/turns/' + turn['id'] + '/cancel', {'version': 1})
    assert cancelled.status_code == 200 and cancelled.json()['turns'][-1]['status'] == 'cancelled'
    assert client.delete(base + '/materials/' + asset['id'] + '?conversationId=' + channel,
        headers=HEADERS).status_code == 200
    next_turn = send(client, task, key='generate', conversationId=channel).json()['turns'][-1]
    image = output(store)
    finish(factory, next_turn, [image])
    assert post(client, task, '/studio/archive', {
        'conversationId': channel, 'pictureIds': [image['id']], 'sku': 'A'}, 'archive').status_code == 200
    revised = send(client, task, key='revise', conversationId=channel,
        referencePictureIds=[image['id']], imageEdits=[{'pictureId': image['id'], 'text': '调整'}])
    assert revised.status_code == 200, revised.text
    finish(factory, revised.json()['turns'][-1])
    completed = post(client, task, '/studio/complete', {'version': 2}, 'complete')
    assert completed.status_code == 200 and completed.json()['completed']
    assert send(client, task, key='while-completed').status_code == 409
    assert post(client, task, '/studio/reopen', {'version': 3}, 'reopen').status_code == 200
    assert send(client, task, key='continue', conversationId=channel).status_code == 200
    empty = post(client, task, '/studio/conversations', {'name': '删除候选'}, 'empty').json()
    deleted = client.request('DELETE', base + '/conversations/' + empty['conversationId'],
        json={'version': 1}, headers={**HEADERS, 'Idempotency-Key': 'delete-channel'})
    assert deleted.status_code == 200, deleted.text


def test_unrelated_grant_reads_artifacts_but_all_mutations_are_denied(studio, monkeypatch):
    client, factory, actor, task, material, store = studio
    base = ROOT + '/tasks/' + task['id'] + '/studio'
    uploaded = client.post(base + '/files', files={'file': ('note.txt', b'content')}, headers=HEADERS).json()
    sent = send(client, task, attachmentIds=[uploaded['id'], 'task:' + material['id']]).json()
    channel, turn = sent['conversationId'], sent['turns'][-1]
    image = output(store)
    finish(factory, turn, [image])
    file_id = uuid4()
    with factory.begin() as session:
        row = OutputFile(id=file_id, task_id=UUID(task['id']), turn_id=UUID(turn['id']),
            name='result.txt', bucket='test', object_key='workflow-result', content_type='text/plain',
            checksum=sha256(b'output').hexdigest(), size_bytes=6, source_path='/work/result.txt')
        session.add(row)
        store.put(row, b'output')
    archived = post(client, task, '/studio/archive', {'pictureIds': [image['id']], 'sku': 'A'}, 'archive').json()
    archive_id = archived['archiveId']
    live = send(client, task, key='active').json()['turns'][-1]
    change_roles(factory, actor, ('designer',))
    grant(actor)
    relate(factory, task, actor, UUID(task['designer']['id']), 'unrelated')
    # Archive ownership is a task snapshot and updated on normal reassignment.
    from app.overseas.archives.models import Archive
    with factory.begin() as session:
        record = session.get(Archive, UUID(archive_id))
        record.created_by = record.designer_id = UUID(task['designer']['id'])
    reads = [base, base + '/events', base + '/transcript', uploaded['url'],
        ROOT + '/materials/' + material['id'] + '/content',
        base + '/pictures/' + image['id'] + '/content', base + '/outputs/' + str(file_id) + '/content',
        ROOT + '/tasks/' + task['id'] + '/materials', ROOT + '/archives/' + archive_id,
        ROOT + '/archives/' + archive_id + '/download', ROOT + '/tasks/' + task['id'] + '/plans',
        ROOT + '/tasks/' + task['id'] + '/pictures', ROOT + '/tasks/' + task['id'] + '/jobs',
        ROOT + '/tasks/' + task['id'] + '/execution-events']
    for path in reads:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert client.get(ROOT + '/archives').json()['total'] == 1
    assert client.get(ROOT + '/management/usage').json()['jobs'] == 0
    assert client.get(ROOT + '/tasks/' + task['id']).json()['capabilities'] == ['task.read']
    for path in (uploaded['url'], base + '/pictures/' + image['id'] + '/content',
                 base + '/outputs/' + str(file_id) + '/content'):
        assert client.head(path).status_code == 200
    writes = [('/studio/turns', {'text': '不能写'}), ('/studio/conversations', {'name': '不能创建'}),
        ('/studio/turns/' + live['id'] + '/cancel', {'version': 1}),
        ('/studio/archive', {'pictureIds': [image['id']], 'sku': 'A'}),
        ('/studio/complete', {'version': 2}), ('/studio/reopen', {'version': 2}),
        ('/requirements-review', {'version': 2, 'decision': 'approve'}),
        ('/analysis', {'version': 2})]
    for suffix, body in writes:
        response = post(client, task, suffix, body, 'denied-' + suffix)
        assert response.status_code == 403, (suffix, response.text)
    for method, suffix, body in [('PATCH', '/conversations/' + channel, {'name': '不能改', 'version': 1}),
                                 ('DELETE', '/conversations/' + channel, {'version': 1})]:
        assert client.request(method, base + suffix, json=body,
            headers={**HEADERS, 'Idempotency-Key': 'denied'}).status_code == 403
    assert client.delete(base + '/materials/' + uploaded['id'], headers=HEADERS).status_code == 403
    assert client.post(base + '/files', files={'file': ('new.txt', b'new')}, headers=HEADERS).status_code == 403
    assert client.request('DELETE', ROOT + '/archives/' + archive_id,
        json={'deleteToken': '0' * 64}, headers=HEADERS).status_code == 403
    assert client.post(ROOT + '/jobs/' + live['jobId'] + '/cancel',
        json={'version': 1}, headers=HEADERS).status_code == 403


def test_recovery_list_read_and_receive_write_rechecked_at_native_boundary(studio, monkeypatch, tmp_path):
    client, factory, actor, task, _, store = studio
    sent = send(client, task).json()
    channel = sent['conversationId']
    finish(factory, sent['turns'][-1])
    get_settings().codex_execution_root = str(tmp_path)
    work = tmp_path / 'studio' / channel / 'persistent' / 'work'
    work.mkdir(parents=True)
    (work / 'saved.txt').write_text('original output', encoding='utf-8')
    change_roles(factory, actor, ('designer',))
    grant(actor)
    relate(factory, task, actor, UUID(task['designer']['id']), 'unrelated')
    def native(operation, actor_id, task_id, conversation_id, files=()):
        return recovery_transport.handle_native(factory, dict(id=uuid4(), operation=operation,
            actor_id=actor_id, task_id=task_id, conversation_id=conversation_id,
            expires_at=time.time() + 20, files=[item.model_dump() for item in files]), store)
    monkeypatch.setattr(recovery_transport, 'request', native)
    base = ROOT + '/tasks/' + task['id'] + '/studio/conversations/' + channel
    result = client.get(base + '/recoverable-files')
    assert result.status_code == 200 and result.json()['items'][0]['name'] == 'saved.txt'
    assert client.post(base + '/recover-files', json={'files': [{'id': 'candidate', 'version': 'v1'}]},
        headers=HEADERS).status_code == 403
    from app.overseas.studio.recovery_transport import Selection
    with pytest.raises(HTTPException) as denied:
        native('receive', actor, UUID(task['id']), UUID(channel), [Selection(id='candidate', version='v1')])
    assert denied.value.status_code == 403
    for change in ('revoke', 'disable'):
        get_settings().workflow_collaborator_member_ids = frozenset() if change == 'revoke' else frozenset((actor,))
        if change == 'disable':
            with factory.begin() as session:
                session.get(Member, actor).status = 'disabled'
        with pytest.raises(HTTPException) as denied:
            native('available', actor, UUID(task['id']), UUID(channel))
        assert denied.value.status_code == 403
        assert client.get(base + '/recoverable-files').status_code == 403
