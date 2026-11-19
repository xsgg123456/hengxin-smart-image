"""Member task lists and strictly scoped, read-only views through real HTTP and PostgreSQL."""
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.main import app
from app.modules.domestic_studio.task_models import Task, TaskRequest
from app.modules.domestic_studio.turn_models import OutputFile, Turn
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from test_domestic_studio_admin_pg import business_snapshot
from test_domestic_studio_bindings_pg import database
from test_domestic_studio_http_pg import client_env
from test_domestic_tasks_pg import HEADERS, ROOT, new, studio
from test_domestic_turns_pg import context


def test_member_list_uses_all_owners_for_search_status_and_pages(client_env):
    client, _, _, identity, owner, peer, _, _ = client_env
    first = new(client, '项目-甲', 'case')
    completed = client.patch(ROOT + '/' + first['id'], json={'version': 1, 'completed': True}, headers=HEADERS)
    assert completed.status_code == 200
    new(client, '项目-另一业务')
    identity['id'] = peer
    second = new(client, '项目-乙', 'case')
    new(client, '名称不匹配', 'case')
    for viewer in (owner, peer):
        identity['id'] = viewer
        params = dict(workspace='case', search='项目-', pageSize=1)
        pages = [client.get(ROOT, params=params | {'page': page}).json() for page in (1, 2)]
        assert {result['items'][0]['id'] for result in pages} == {first['id'], second['id']}
        for result in pages:
            assert result['total'] == 2 and result['counters'] == dict(total=2, active=1, completed=1)
        active = client.get(ROOT, params=params | {'status': 'active'}).json()
        assert active['total'] == 1 and [row['id'] for row in active['items']] == [second['id']]
        assert active['counters'] == pages[0]['counters']
        assert client.get(ROOT, params=params).headers['cache-control'] == 'private, no-store'


def test_business_view_checks_scope_and_only_exposes_submitted_files(client_env):
    client, factory, _, identity, owner, peer, _, other_channel = client_env
    task = new(client, '共享任务')
    sibling = new(client, '同业务另一任务')
    task_id = task['id']
    private = studio(task)
    channel = client.post(private + '/conversations', headers=HEADERS, json={'name': '共享方案'}).json()['conversationId']
    def upload(name):
        response = client.post(private + '/files', params={'conversationId': channel}, headers=HEADERS,
            files={'file': (name, name.encode(), 'text/plain')})
        assert response.status_code == 200
        return response.json()
    submitted, draft = upload('submitted.txt'), upload('draft.txt')
    sent = client.post(private + '/turns', headers=HEADERS, json={
        'conversationId': channel, 'text': '已提交要求', 'attachmentIds': [submitted['id']]})
    assert sent.status_code == 200, sent.text
    result_id = uuid4()
    store = app.dependency_overrides[get_store]()
    result_bytes = b'saved result'
    turn_id = sent.json()['turns'][0]['id']
    with factory.begin() as session:
        session.add(OutputFile(id=result_id, turn_id=UUID(turn_id), name='result.txt',
            content_type='text/plain', size_bytes=len(result_bytes), checksum=sha256(result_bytes).hexdigest(),
            bucket='private', object_key=str(result_id), source_path='/private/file.txt'))
        store.objects[('private', str(result_id))] = result_bytes
        session.get(UserRecord, peer).role = 'operator'
    identity['id'] = peer
    before = business_snapshot(factory)
    with factory() as session:
        tasks = list(session.execute(select(Task.__table__)))
        receipts = list(session.execute(select(TaskRequest.__table__)))
    view = f'{ROOT}/{task_id}/view/camera'
    session_url = f'{view}/sessions/{channel}'
    detail = client.get(view)
    assert detail.status_code == 200 and detail.json()['sessions'][0]['id'] == channel
    response = client.get(session_url)
    assert response.status_code == 200 and response.headers['cache-control'] == 'private, no-store'
    data = response.json()['workspace']
    assert [a['id'] for a in data['materials']] == [submitted['id']]
    assert data['turns'][0]['text'] == '已提交要求' and 'draft.txt' not in response.text
    attachment = data['turns'][0]['attachments'][0]['url']
    output = data['turns'][0]['outputs'][0]['url']
    assert attachment.startswith(session_url + '/files/') and output.startswith(session_url + '/outputs/')
    assert client.get(attachment).content == b'submitted.txt' and client.get(output).content == result_bytes
    assert client.head(attachment).headers['cache-control'] == 'private, no-store'
    assert client.get(session_url + '/transcript').status_code == 200
    assert client.get(attachment.replace(submitted['id'][7:], draft['id'][7:])).status_code == 404
    for path in (session_url, session_url + '/transcript', attachment, output):
        assert client.get(path.replace('view/camera', 'view/case')).status_code == 404
        assert client.get(path.replace(task_id, sibling['id'])).status_code == 404
        assert client.get(path.replace(channel, str(other_channel))).status_code == 404
    assert client.get(view.replace('view/camera', 'view/case')).status_code == 404
    assert client.get(submitted['url']).status_code == client.get(private).status_code == 404
    assert client.get('/api/v1/management/domestic-studio/tasks').status_code == 403
    assert client.get('/api/v1/management/domestic-studio/sessions/' + channel).status_code == 403
    assert client.post(private + '/turns', headers=HEADERS, json={'conversationId': channel, 'text': '禁止代发'}).status_code == 404
    assert client.post(private + '/turns/' + turn_id + '/cancel', headers=HEADERS, json={'version': 1}).status_code == 404
    assert client.patch(ROOT + '/' + task_id, headers=HEADERS, json={'name': '禁止改名', 'version': 1}).status_code == 404
    assert client.request('DELETE', ROOT + '/' + task_id, headers=HEADERS, json={'version': 1}).status_code == 404
    assert client.patch(session_url, headers=HEADERS, json={'name': '禁止改名'}).status_code == 405
    assert business_snapshot(factory) == before
    with factory.begin() as session:
        assert tasks == list(session.execute(select(Task.__table__)))
        assert receipts == list(session.execute(select(TaskRequest.__table__)))
        session.get(UserRecord, peer).role = 'super_admin'
    assert client.get(view).status_code == 200
    assert client.patch(ROOT + '/' + task_id, headers=HEADERS, json={'completed': True, 'version': 1}).status_code == 404
    with factory.begin() as session:
        session.get(UserRecord, peer).status = 'disabled'
    for path in (view, session_url, session_url + '/transcript', attachment, output):
        assert client.get(path).status_code == 403
