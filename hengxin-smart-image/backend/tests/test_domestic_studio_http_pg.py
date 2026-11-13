"""Actual domestic HTTP routes with isolated PostgreSQL and fake object storage."""
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.models import Job, Outbox
from app.modules.auth.dependencies import get_identity_id
from app.modules.domestic_studio.management_router import get_catalog
from app.modules.domestic_studio.turn_models import OutputFile, Transcript, Turn
from app.storage.minio_store import get_store
from test_domestic_files_pg import Store
from test_domestic_studio_bindings_pg import database
from test_domestic_turns_pg import bind, context


@pytest.fixture
def client_env(context, database):
    factory, catalog, skill, first, second, channel, other_channel = context
    for model in (OutputFile, Transcript):
        model.__table__.create(database)
    class ObjectStore(Store):
        def stat(self, row):
            return len(self.objects[(row.bucket, row.object_key)])
    store, identity = ObjectStore(), {'id': first}
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_session] = db
    app.dependency_overrides[get_identity_id] = lambda: identity['id']
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    yield client, factory, skill, identity, first, second, channel, other_channel
    client.close()
    for dependency in (get_session, get_identity_id, get_catalog, get_store):
        app.dependency_overrides.pop(dependency, None)


def test_http_sessions_and_files_are_private_with_no_default_skill(client_env):
    client, factory, skill, identity, first, second, channel, _ = client_env
    root = '/api/v1/domestic-studio/workspaces/camera'
    response = client.get(root)
    assert response.status_code == 200 and response.json()['fixedSkillReady'] is False
    assert response.json()['turns'] == []
    missing = client.post(root + '/turns', headers={'X-HX-Request': '1', 'Idempotency-Key': 'send'},
                          json={'conversationId': str(channel), 'text': '我的要求', 'skillId': None})
    assert missing.status_code == 200
    assert missing.json()['turns'][0]['skillName'] is None
    with factory.begin() as session:
        bind(session, skill['id'])
    headers = {'X-HX-Request': '1', 'Idempotency-Key': 'send'}
    result = client.post(root + '/turns', headers=headers,
                         json={'conversationId': str(channel), 'text': '我的要求', 'skillId': None})
    assert result.status_code == 200 and result.json()['turns'][0]['text'] == '我的要求'
    assert result.json()['fixedSkillReady'] is True
    assert result.json()['skills'][0]['id'] == skill['id']
    uploaded = client.post(root + f'/files?conversationId={channel}', headers={'X-HX-Request': '1'},
                           files={'file': ('test.txt', b'private bytes', 'text/plain')})
    assert uploaded.status_code == 200
    path = uploaded.json()['url']
    assert client.head(path).status_code == 200
    identity['id'] = second
    assert client.get(root, params={'conversationId': str(channel)}).status_code == 404
    assert client.head(path).status_code == 404
    turn_id = UUID(result.json()['turns'][0]['id'])
    assert client.post(root + f'/turns/{turn_id}/cancel', headers={'X-HX-Request': '1'},
                       json={'version': 1}).status_code == 404
    identity['id'] = first
    assert client.post('/api/v1/domestic-studio/workspaces/wrong/conversations',
                       headers={'X-HX-Request': '1', 'Idempotency-Key': 'new'}, json={}).status_code == 404


def test_http_create_rename_and_idempotency(client_env):
    client, _, _, _, _, _, _, _ = client_env
    root = '/api/v1/domestic-studio/workspaces/case'
    headers = {'X-HX-Request': '1', 'Idempotency-Key': 'new'}
    first = client.post(root + '/conversations', headers=headers, json={'name': '手机壳'})
    repeat = client.post(root + '/conversations', headers=headers, json={'name': '手机壳'})
    assert first.status_code == repeat.status_code == 200
    assert first.json()['conversationId'] == repeat.json()['conversationId']
    identity = first.json()['conversationId']
    changed = client.patch(root + '/conversations/' + identity,
        headers={'X-HX-Request': '1', 'Idempotency-Key': 'rename'}, json={'name': '新手机壳', 'version': 1})
    assert changed.status_code == 200 and changed.json()['conversations'][0]['name'] == '新手机壳'
    assert client.post(root + '/conversations', headers={'Idempotency-Key': 'blocked'}, json={}).status_code == 403


def test_http_recovery_is_private_and_retry_does_not_enqueue_another_model_call(client_env):
    client, factory, skill, identity, first, second, channel, _ = client_env
    root = '/api/v1/domestic-studio/workspaces/camera'
    with factory.begin() as session:
        bind(session, skill['id'])
    response = client.post(root + '/turns', headers={'X-HX-Request': '1', 'Idempotency-Key': 'send-recover'},
                           json={'conversationId': str(channel), 'text': '我的要求'})
    turn_id = UUID(response.json()['turns'][0]['id'])
    with factory.begin() as session:
        turn = session.get(Turn, turn_id)
        turn.dispatched = True
        turn.process_identity = {'node': 'test', 'pid': 123, 'boot': 'boot', 'birth': 'birth'}
        job = session.get(Job, turn.job_id)
        job.status, job.execution_count = 'uncertain', 1
        job_id, version = job.id, turn.version
        session.get(Outbox, job.id).completed_at = job.created_at
    headers = {'X-HX-Request': '1'}
    identity['id'] = second
    assert client.post(root + f'/turns/{turn_id}/recover', headers=headers, json={'version': version}).status_code == 404
    identity['id'] = first
    first_response = client.post(root + f'/turns/{turn_id}/recover', headers=headers, json={'version': version})
    retry = client.post(root + f'/turns/{turn_id}/recover', headers=headers, json={'version': version})
    assert first_response.status_code == retry.status_code == 200
    assert retry.json()['turns'][0]['recoveryRequested'] is True
    with factory() as session:
        assert session.get(Job, job_id).execution_count == 1
        assert session.get(Outbox, job_id).completed_at is None
