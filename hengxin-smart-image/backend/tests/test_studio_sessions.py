"""Independent session API, queue isolation and resumable physical erasure."""
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from app.core.config import get_settings
from app.overseas.studio.models import Conversation, ConversationDeletion, Turn, Transcript, Upload, Picture
from app.overseas.studio.conversation_cleanup import cleanup_once
from app.overseas.execution.models import Job
from app.overseas.execution import claims
from app.overseas.tasks.models import Task
from test_overseas_tasks import overseas, ROOT, HEADERS, create, payload
from test_overseas_materials import materials
from test_overseas_studio import studio, send, finish
from test_overseas_task_deletion import deletion, generated, archived
from test_overseas_plans import post
from test_overseas_assignment import change_roles
from studio_sessions_helpers import base, channel, selected, upload_private, mutate


def test_named_sessions_cap_idempotency_and_old_history_over_limit(studio):
    client, factory, _, task, _, _ = studio
    ids = [channel(client, task, str(i), f'会话 {i}') for i in range(10)]
    assert len(set(ids)) == 10
    assert post(client, task, '/studio/conversations', {}, 'over').status_code == 409
    assert channel(client, task, '0', '会话 0') == ids[0]
    renamed = mutate(client, task, ids[0], 'PATCH', dict(name='首图方案', version=1))
    assert renamed.status_code == 200 and renamed.json()['conversations'][0]['name'] == '首图方案'
    assert mutate(client, task, ids[0], 'PATCH', dict(name='首图方案', version=1)).status_code == 200
    assert mutate(client, task, ids[0], 'PATCH', dict(name='过期', version=1), 'stale').status_code == 409
    for name in (' ', 'x' * 31, '\n'):
        assert mutate(client, task, ids[0], 'PATCH', dict(name=name, version=2), name).status_code == 422
    with factory.begin() as session:
        session.add(Conversation(task_id=UUID(task['id']), name='历史超限会话'))
    assert len(selected(client, task, ids[0])['conversations']) == 11
    assert post(client, task, '/studio/conversations', {}, 'still-over').status_code == 409


def test_parallel_sessions_private_inputs_transcript_and_claims(studio):
    client, factory, _, task, material, _ = studio
    a = channel(client, task)
    first = send(client, task, conversationId=a).json()['turns'][0]
    b = channel(client, task, 'second')  # Creating while another session is queued is allowed.
    private = upload_private(client, task, a)
    assert private['id'] in {row['id'] for row in selected(client, task, a)['materials']}
    assert private['id'] not in {row['id'] for row in selected(client, task, b)['materials']}
    assert send(client, task, key='foreign', conversationId=b, attachmentIds=[private['id']]).status_code == 404
    second = send(client, task, key='parallel', conversationId=b,
        attachmentIds=['task:' + material['id']]).json()['turns'][0]
    assert send(client, task, key='busy', conversationId=a).status_code == 409
    assert claims.claim(factory, first['jobId']) and claims.claim(factory, second['jobId'])
    with factory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.status == 'running')) == 2
        for turn in (first, second):
            session.add(Transcript(task_id=UUID(task['id']), turn_id=UUID(turn['id']),
                item_id='message', kind='message', text=turn['conversationId'], state='completed'))
    data = selected(client, task, a)
    assert data['activeConversationCount'] == 2 and len(data['turns']) == 1
    assert {c['status'] for c in data['conversations']} == {'running'}
    transcript = client.get(base(task) + '/transcript', params={'conversationId': b}).json()
    assert [row['text'] for row in transcript['items']] == [b]
    assert post(client, task, '/studio/complete', {'version': 2}, 'busy').status_code == 409
    stopped = post(client, task, '/studio/turns/' + first['id'] + '/cancel', {'version': 2})
    assert stopped.status_code == 200
    assert selected(client, task, b)['turns'][0]['status'] == 'running'


def test_private_visibility_and_reference_images_do_not_cross_sessions(studio):
    client, factory, _, task, _, store = studio
    from test_overseas_studio import output
    a, b = channel(client, task), channel(client, task, 'second')
    pa, pb = upload_private(client, task, a), upload_private(client, task, b)
    assert client.delete(base(task) + '/materials/' + pa['id'], params={'conversationId': a}, headers=HEADERS).status_code == 200
    assert pb['id'] in {row['id'] for row in selected(client, task, b)['materials']}
    assert upload_private(client, task, a)['materialState'] == 'restored'
    turn = send(client, task, conversationId=a).json()['turns'][0]
    picture = output(store)
    finish(factory, turn, [picture])
    assert send(client, task, key='cross-picture', conversationId=b, referencePictureIds=[picture['id']]).status_code == 404
    assert post(client, task, '/studio/archive', dict(conversationId=b, pictureIds=[picture['id']], sku='A'), 'cross-archive').status_code == 404


def test_erase_private_files_records_and_preserve_archives_other_sessions(deletion):
    client, factory, _, task, material, store = deletion
    pictures = generated(deletion)
    archive = archived(deletion, pictures[:1])
    a = client.get(base(task)).json()['conversationId']
    pa = upload_private(client, task, a)
    b = channel(client, task, 'other')
    pb = upload_private(client, task, b, b'other')
    root = Path(get_settings().codex_execution_root) / 'studio'
    for identity in (a, b):
        (root / identity).mkdir(parents=True)
        (root / identity / 'session.jsonl').write_bytes(b'private history')
    before = client.get(ROOT + '/archives/' + archive['id']).json()
    assert before['pictures'][0]['sourceConversationId'] == a
    pending = mutate(client, task, a, 'DELETE', {'version': 2})
    assert pending.status_code == 200
    assert next(c for c in pending.json()['conversations'] if c['id'] == a)['deletionStatus'] == 'deleting'
    assert send(client, task, key='deleting', conversationId=a).status_code == 409
    assert mutate(client, task, a, 'PATCH', dict(name='不可修改', version=3), 'rename').status_code == 409
    assert cleanup_once(factory, store) == 1
    assert not (root / a).exists() and (root / b / 'session.jsonl').read_bytes() == b'private history'
    assert client.get(pa['url']).status_code == 404 and client.get(pb['url']).content == b'other'
    assert client.get(ROOT + '/materials/' + material['id'] + '/content').status_code == 200
    assert client.get(base(task), params={'conversationId': a}).status_code == 410
    assert mutate(client, task, a, 'DELETE', {'version': 2}).status_code == 410
    assert client.get(before['pictures'][0]['url']).status_code == 200
    assert client.get(ROOT + '/archives/' + archive['id']).json()['pictureCount'] == 1
    with factory() as session:
        for model in (Turn, Picture, Job):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        receipt = session.get(ConversationDeletion, UUID(a))
        assert receipt.status == 'deleted' and receipt.manifest == {}
    assert channel(client, task, 'replacement') not in (a, b)


def test_failed_delete_retains_slot_and_retries_without_false_success(deletion):
    client, factory, _, task, _, store = deletion
    identity = channel(client, task)
    private = upload_private(client, task, identity)
    assert mutate(client, task, identity, 'DELETE', dict(version=1)).status_code == 200
    store.fail_remove = True
    assert cleanup_once(factory, store) == 0
    row = selected(client, task, identity)['conversations'][0]
    assert row['deletionStatus'] == 'delete_failed' and row['deletionError']
    assert client.get(private['url']).status_code == 200
    # Replaying an unknown first response only verifies it; a fresh action retries.
    assert mutate(client, task, identity, 'DELETE', dict(version=1)).status_code == 200
    assert selected(client, task, identity)['conversations'][0]['deletionStatus'] == 'delete_failed'
    store.fail_remove = False
    assert mutate(client, task, identity, 'DELETE', dict(version=2), 'retry').status_code == 200
    assert cleanup_once(factory, store) == 1
    assert client.get(private['url']).status_code == 404


def test_session_ownership_permissions_running_delete_and_completed_readonly(studio):
    client, factory, actor, task, _, _ = studio
    a = channel(client, task)
    other = create(client, payload(UUID(task['designer']['id'])), 'other').json()
    assert client.get(base(other), params={'conversationId': a}).status_code == 404
    assert mutate(client, other, a, 'PATCH', dict(name='盗改', version=1)).status_code == 404
    turn = send(client, task, conversationId=a).json()['turns'][0]
    assert mutate(client, task, a, 'DELETE', dict(version=1)).status_code == 409
    finish(factory, turn)
    with factory.begin() as session:
        session.get(Task, UUID(task['id'])).status = 'completed'
    assert selected(client, task, a)['completed']
    assert mutate(client, task, a, 'PATCH', dict(name='冻结', version=1)).status_code == 409
    assert mutate(client, task, a, 'DELETE', dict(version=1)).status_code == 409
    change_roles(factory, actor, ('designer',))
    assert client.get(base(task), params={'conversationId': a}).status_code == 403


def test_legacy_cross_session_picture_reference_survives_source_deletion(deletion):
    client, factory, _, task, _, store = deletion
    original = generated(deletion, count=1)[0]
    a = client.get(base(task)).json()['conversationId']
    b = channel(client, task, 'legacy-consumer')
    consumer = send(client, task, key='legacy-reference', conversationId=b).json()['turns'][0]
    finish(factory, consumer)
    # This was legal before sessions had independent input authorization.
    with factory.begin() as session:
        turn = session.get(Turn, UUID(consumer['id']))
        turn.reference_ids = [original['id']]
        job = session.get(Job, turn.job_id)
        job.payload = {**job.payload, 'inputs': [{key: original[key] for key in
            ('id', 'name', 'bucket', 'object_key', 'content_type', 'size_bytes', 'checksum')}]}
    assert mutate(client, task, a, 'DELETE', dict(version=2)).status_code == 200
    assert cleanup_once(factory, store) == 1
    reference = selected(client, task, b)['turns'][0]['referencePictures'][0]
    assert client.get(reference['url']).status_code == 200
    with factory() as session:
        retained = session.get(Picture, UUID(original['id']))
        assert retained.turn_id is None and retained.origin_turn_id
    assert mutate(client, task, b, 'DELETE', dict(version=2), 'consumer-delete').status_code == 200
    assert cleanup_once(factory, store) == 1
    assert original['object_key'] not in store.data
    with factory() as session:
        assert session.get(Picture, UUID(original['id'])) is None


def test_deletion_rejects_unverified_process_and_linked_workspace(deletion, tmp_path):
    client, factory, _, task, _, store = deletion
    identity = channel(client, task)
    turn = send(client, task, conversationId=identity).json()['turns'][0]
    finish(factory, turn)
    with factory.begin() as session:
        session.get(Job, UUID(turn['jobId'])).process_exited = False
    assert mutate(client, task, identity, 'DELETE', dict(version=2)).status_code == 200
    assert cleanup_once(factory, store) == 0
    with factory.begin() as session:
        session.get(Job, UUID(turn['jobId'])).process_exited = True
    root = Path(get_settings().codex_execution_root) / 'studio' / identity
    root.mkdir(parents=True)
    outside = tmp_path / 'protected'
    outside.mkdir()
    (outside / 'input.txt').write_bytes(b'protected')
    try:
        (root / 'linked').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('symlink creation unavailable on this host')
    assert mutate(client, task, identity, 'DELETE', dict(version=3), 'retry').status_code == 200
    assert cleanup_once(factory, store) == 0
    assert (outside / 'input.txt').read_bytes() == b'protected'


@pytest.mark.parametrize('accepted', [False, True])
def test_legacy_send_hint_preserves_hash_receipt_and_original_session(studio, accepted):
    from app.core.idempotency import fingerprint_payload
    from app.overseas.tasks.models import TaskRequest
    client, factory, _, task, _, _ = studio
    a = channel(client, task)
    body = dict(text='旧版原会话请求', skillId=None, attachmentIds=[], referencePictureIds=[])
    headers = {**HEADERS, 'Idempotency-Key': 'legacy-send'}
    if accepted:
        first = client.post(base(task) + '/turns', json=body, headers=headers)
        assert first.status_code == 200, first.text
        # Before this release receipts had no conversation association.
        with factory.begin() as session:
            session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send')).conversation_id = None
    b = channel(client, task, 'latest-b')
    response = client.post(base(task) + '/turns', params={'conversationId': a}, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['conversationId'] == a
    assert len(response.json()['turns']) == 1
    assert selected(client, task, b)['turns'] == []
    replay = client.post(base(task) + '/turns', params={'conversationId': a}, json=body, headers=headers)
    assert replay.status_code == 200 and replay.json()['turns'] == response.json()['turns']
    assert client.post(base(task) + '/turns', params={'conversationId': b}, json=body, headers=headers).status_code == 409
    with factory() as session:
        receipt = session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send'))
        assert receipt.body_hash == fingerprint_payload(body)
        assert receipt.conversation_id == UUID(a)
        assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_legacy_send_hint_rejects_deleted_foreign_and_conflicting_body(studio):
    from app.overseas.tasks.models import TaskRequest
    client, factory, _, task, _, store = studio
    a, b = channel(client, task), channel(client, task, 'b')
    body, headers = {'text': '旧版待核实'}, {**HEADERS, 'Idempotency-Key': 'legacy-send'}
    assert client.post(base(task) + '/turns', params={'conversationId': a},
        json={**body, 'conversationId': b}, headers=headers).status_code == 409
    other = create(client, payload(UUID(task['designer']['id'])), 'other').json()
    with factory.begin() as session:
        row = session.get(Task, UUID(other['id']))
        row.status, row.requirements_approved = 'studio', True
    assert client.post(base(other) + '/turns', params={'conversationId': a}, json=body, headers=headers).status_code == 404
    assert mutate(client, task, a, 'DELETE', {'version': 1}).status_code == 200
    assert cleanup_once(factory, store) == 1
    assert client.post(base(task) + '/turns', params={'conversationId': a}, json=body, headers=headers).status_code == 410
    assert client.post(base(task) + '/turns', params={'conversationId': str(uuid4())}, json=body, headers=headers).status_code == 404
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send')) is None


def test_legacy_accepted_receipt_cannot_replay_into_deleted_or_foreign_hint(studio):
    from app.overseas.tasks.models import TaskRequest
    client, factory, _, task, _, store = studio
    a = channel(client, task)
    response = send(client, task, key='accepted-old')
    assert response.status_code == 200
    finish(factory, response.json()['turns'][0])
    with factory.begin() as session:
        receipt = session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send'))
        receipt.conversation_id = None
        digest = receipt.body_hash
    b = channel(client, task, 'b')
    assert mutate(client, task, a, 'DELETE', {'version': 2}).status_code == 200
    assert cleanup_once(factory, store) == 1
    headers = {**HEADERS, 'Idempotency-Key': 'accepted-old'}
    assert client.post(base(task) + '/turns', params={'conversationId': a},
        json={'text': '设计产品'}, headers=headers).status_code == 410
    assert selected(client, task, b)['turns'] == []
    with factory() as session:
        receipt = session.scalar(select(TaskRequest).where(TaskRequest.operation == 'studio_send'))
        assert receipt.body_hash == digest and receipt.conversation_id is None
        assert session.scalar(select(func.count()).select_from(Job)) == 0
