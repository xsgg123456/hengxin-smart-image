"""Real HTTP task ownership, lifecycle, request receipts and admin boundaries."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Job
from app.modules.auth.application_models import MemberAudit
from app.modules.domestic_studio import conversation_cleanup, task_service
from app.modules.domestic_studio.archive_models import Archive, ArchiveDeletion, ArchiveFile
from app.modules.domestic_studio.conversation_models import Conversation, ConversationDeletion, ConversationRequest
from app.modules.domestic_studio.task_models import Task
from app.modules.domestic_studio.task_schemas import NewTask
from app.modules.domestic_studio.turn_models import Turn
from app.resource_models import UserRecord
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import context
from test_domestic_studio_http_pg import client_env

ROOT = '/api/v1/domestic-studio/tasks'
HEADERS = {'X-HX-Request': '1', 'Idempotency-Key': 'request'}


def new(client, name='产品任务', workspace='camera', key=None):
    response = client.post(ROOT, json=dict(name=name, workspace=workspace),
                           headers={**HEADERS, 'Idempotency-Key': key or str(uuid4())})
    assert response.status_code == 200, response.text
    return response.json()


def studio(task):
    return ROOT + '/' + task['id'] + '/studio'


def test_task_crud_zero_sessions_filter_counts_and_idempotency(client_env):
    client, factory, _, identity, owner, other, _, _ = client_env
    task = new(client, key='stable')
    assert new(client, key='stable')['id'] == task['id']
    assert task['conversationCount'] == 0 and task['version'] == 1
    result = client.get(studio(task)).json()
    assert result['taskId'] == task['id'] and result['conversations'] == []
    assert client.post(ROOT, json=dict(name='不同', workspace='camera'), headers={**HEADERS,
        'Idempotency-Key': 'stable'}).status_code == 409
    for invalid in ('', ' ' * 4, 'x' * 61, 'bad\nname'):
        assert client.post(ROOT, json=dict(name=invalid, workspace='camera'), headers=HEADERS).status_code == 422
    response = client.patch(ROOT + '/' + task['id'], json={'version': 1, 'name': '已改名'}, headers=HEADERS)
    assert response.status_code == 200 and response.json()['version'] == 2
    assert client.patch(ROOT + '/' + task['id'], json={'version': 1, 'name': '已改名'}, headers=HEADERS).json()['version'] == 2
    assert client.patch(ROOT + '/' + task['id'], json={'version': 1, 'name': '冲突'},
        headers={**HEADERS, 'Idempotency-Key': 'stale'}).status_code == 409
    listed = client.get(ROOT, params={'workspace': 'camera', 'search': '已改名', 'pageSize': 1}).json()
    assert listed['total'] == listed['counters']['active'] == 1
    assert listed['items'][0]['ownerId'] == str(owner)
    assert client.get(ROOT).status_code == 422
    identity['id'] = other
    assert client.get(ROOT + '/' + task['id']).status_code == 404
    assert client.get(studio(task)).status_code == 404


def test_task_scope_rejects_cross_task_conversation_turn_upload_and_reads(client_env):
    client, factory, _, _, _, _, _, _ = client_env
    one, two = new(client), new(client)
    response = client.post(studio(one) + '/conversations', json={'name': '方案甲'}, headers=HEADERS)
    assert response.status_code == 200, response.text
    channel = response.json()['conversationId']
    assert client.post('/api/v1/domestic-studio/workspaces/camera/conversations', json={}, headers=HEADERS).status_code == 422
    assert client.get(studio(two), params={'conversationId': channel}).status_code == 404
    assert client.get(studio(two) + '/transcript', params={'conversationId': channel}).status_code == 404
    assert client.post(studio(two) + '/files', params={'conversationId': channel}, headers=HEADERS,
        files={'file': ('secret.txt', b'secret', 'text/plain')}).status_code == 404
    upload = client.post(studio(one) + '/files', params={'conversationId': channel}, headers=HEADERS,
        files={'file': ('secret.txt', b'secret', 'text/plain')})
    assert upload.status_code == 200, upload.text
    url = upload.json()['url']
    assert '/tasks/' + one['id'] + '/studio/' in url
    assert client.get(url).status_code == 200
    assert client.get(url.replace(one['id'], two['id'])).status_code == 404
    sent = client.post(studio(one) + '/turns', json={'conversationId': channel, 'text': '生成'}, headers=HEADERS)
    assert sent.status_code == 200, sent.text
    turn_id = sent.json()['turns'][0]['id']
    assert client.post(studio(two) + '/turns/' + turn_id + '/cancel', json={'version': 1}, headers=HEADERS).status_code == 404
    assert client.patch(ROOT + '/' + one['id'], json={'version': 1, 'completed': True}, headers=HEADERS).status_code == 409
    assert client.request('DELETE', ROOT + '/' + one['id'], json={'version': 1}, headers=HEADERS).status_code == 409


def test_status_filter_preserves_counters_for_member_business_and_search(client_env, database):
    client, factory, _, identity, owner, admin, _, _ = client_env
    MemberAudit.__table__.create(database)
    new(client, name='统计-进行中')
    task = new(client, name='统计-已完成')
    new(client, name='名称范围之外')
    new(client, name='统计-其他业务', workspace='case')
    assert client.patch(ROOT + '/' + task['id'], json={'version': 1, 'completed': True}, headers=HEADERS).status_code == 200
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'super_admin'
    for management in (False, True):
        if management:
            identity['id'] = admin
            new(client, name='统计-其他成员')
        root = '/api/v1/management/domestic-studio/tasks' if management else ROOT
        for status in ('active', 'completed'):
            params = dict(workspace='camera', search='统计-', status=status, pageSize=1)
            if management:
                params['ownerId'] = str(owner)
            response = client.get(root, params=params)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['total'] == len(result['items']) == 1
            assert result['counters'] == {'total': 2, 'active': 1, 'completed': 1}
            assert result['items'][0]['completed'] is (status == 'completed')


def test_completion_blocks_new_and_legacy_writes_and_can_reopen(client_env, monkeypatch):
    client, factory, _, _, _, _, _, _ = client_env
    task = new(client)
    channel = client.post(studio(task) + '/conversations', json={}, headers=HEADERS).json()['conversationId']
    complete = client.patch(ROOT + '/' + task['id'], json={'version': 1, 'completed': True}, headers=HEADERS)
    assert complete.status_code == 200 and complete.json()['completed']
    assert client.get(studio(task)).json()['completed']
    def forbidden_recovery(*args, **kwargs):
        raise AssertionError('Completed task must be rejected before native file recovery')
    monkeypatch.setattr('app.modules.domestic_studio.router.recovery_transport.request', forbidden_recovery)
    for root in (studio(task), '/api/v1/domestic-studio/workspaces/camera'):
        assert client.post(root + '/turns', json={'conversationId': channel, 'text': '禁止'}, headers=HEADERS).status_code == 409
        assert client.patch(root + '/conversations/' + channel, json={'name': '禁止', 'version': 1}, headers=HEADERS).status_code == 409
        assert client.post(root + '/files', params={'conversationId': channel}, headers=HEADERS,
            files={'file': ('bad.txt', b'blocked', 'text/plain')}).status_code == 409
        assert client.post(root + '/conversations/' + channel + '/recover-files',
            json={'files': [{'id': 'recoverable-output', 'version': 'frozen-version'}]}, headers=HEADERS).status_code == 409
    opened = client.patch(ROOT + '/' + task['id'], json={'version': 2, 'completed': False},
                          headers={**HEADERS, 'Idempotency-Key': 'reopen'})
    assert opened.status_code == 200 and opened.json()['version'] == 3
    assert client.post(studio(task) + '/conversations', json={},
                        headers={**HEADERS, 'Idempotency-Key': 'new'}).status_code == 200


def test_each_task_has_own_ten_session_cap_and_concurrent_task_retry(client_env):
    client, factory, _, _, owner, _, _, _ = client_env
    body = NewTask(name='并发', workspace='camera')
    def attempt(_):
        with factory.begin() as session:
            return task_service.create(session, owner, body, 'parallel').id
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert len(set(pool.map(attempt, range(6)))) == 1
    one, two = new(client), new(client)
    for task in (one, two):
        for index in range(10):
            response = client.post(studio(task) + '/conversations', json={},
                                  headers={**HEADERS, 'Idempotency-Key': str(index)})
            assert response.status_code == 200, response.text
        assert client.post(studio(task) + '/conversations', json={},
            headers={**HEADERS, 'Idempotency-Key': 'overflow'}).status_code == 409


def test_management_task_lists_only_get_and_same_task_siblings(client_env, database):
    client, factory, _, identity, owner, admin, _, _ = client_env
    MemberAudit.__table__.create(database)
    task = new(client)
    for index in range(2):
        result = client.post(studio(task) + '/conversations', json={},
                              headers={**HEADERS, 'Idempotency-Key': str(index)}).json()
    channel = result['conversationId']
    root = '/api/v1/management/domestic-studio/tasks'
    assert client.get(root).status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'super_admin'
    identity['id'] = admin
    listing = client.get(root, params={'ownerId': str(owner), 'search': '产品任务'})
    assert listing.status_code == 200 and listing.headers['cache-control'] == 'private, no-store'
    assert listing.json()['total'] == 1
    detail = client.get(root + '/' + task['id']).json()
    assert len(detail['sessions']) == 2
    old = client.get('/api/v1/management/domestic-studio/sessions/' + channel).json()
    assert len(old['siblingSessions']) == 2 and old['workspace']['taskId'] == task['id']
    for method in ('POST', 'PATCH', 'DELETE'):
        assert client.request(method, root + '/' + task['id'], json={}, headers=HEADERS).status_code == 405
    with factory.begin() as session:
        session.get(UserRecord, admin).role = 'designer'
    assert client.get(root + '/' + task['id']).status_code == 403


def test_task_delete_failure_retry_only_finishes_after_real_cleanup(client_env, database, tmp_path, monkeypatch):
    client, factory, _, _, _, _, _, _ = client_env
    for model in (Archive, ArchiveFile, ArchiveDeletion):
        model.__table__.create(database, checkfirst=True)
    from app.storage.minio_store import get_store
    from app.main import app
    store = app.dependency_overrides[get_store]()
    from types import SimpleNamespace
    monkeypatch.setattr(conversation_cleanup, 'get_settings', lambda: SimpleNamespace(
        codex_execution_root=tmp_path, minio_bucket='test', worker_node_name='test',
        domestic_studio_lock_root=tmp_path / 'locks'))
    from app.overseas.tasks import cleanup_files
    monkeypatch.setattr(cleanup_files, 'get_settings', conversation_cleanup.get_settings)
    task = new(client)
    channel = client.post(studio(task) + '/conversations', json={}, headers=HEADERS).json()['conversationId']
    uploaded = client.post(studio(task) + '/files', params={'conversationId': channel}, headers=HEADERS,
        files={'file': ('delete.txt', b'owned content', 'text/plain')})
    assert uploaded.status_code == 200
    initial_bytes = sum(map(len, store.objects.values()))
    deletion = client.request('DELETE', ROOT + '/' + task['id'], json={'version': 1}, headers=HEADERS)
    assert deletion.status_code == 200 and deletion.json()['status'] == 'deleting'
    original_delete = store.remove
    monkeypatch.setattr(store, 'remove', lambda row: (_ for _ in ()).throw(OSError('failed')))
    assert not conversation_cleanup.process(factory, store, UUID(channel))
    assert client.get(ROOT + '/' + task['id'] + '/deletion').json()['status'] == 'delete_failed'
    assert client.get(ROOT + '/' + task['id']).json()['deletionStatus'] == 'delete_failed'
    monkeypatch.setattr(store, 'remove', original_delete)
    assert client.request('DELETE', ROOT + '/' + task['id'], json={'version': 1}, headers=HEADERS).json()['status'] == 'deleting'
    assert conversation_cleanup.process(factory, store, UUID(channel))
    assert client.get(ROOT + '/' + task['id'] + '/deletion').json()['status'] == 'deleted'
    assert client.get(ROOT + '/' + task['id']).status_code == 404
    assert initial_bytes > 0 and sum(map(len, store.objects.values())) == 0
    with factory() as session:
        assert session.get(Conversation, UUID(channel)) is None
        assert session.get(ConversationDeletion, UUID(channel)).status == 'deleted'
